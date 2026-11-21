#!/usr/bin/env python3
"""Give Garmin naps their own external_id, then delete duplicate sleeps that share one, keeping the newest.

Sleep was matched on external_id only when the stored night was still adjacent to the new one, so a
night re-delivered with times moved past the merge threshold was stored a second time (#2012). Ingest
now looks a night up by (user, provider, external_id) first; this removes the copies stored before.

Garmin naps were stored under their parent sleep's summary id, which the lookup would take for the
night itself. Each gets "<id>-nap-<start epoch>", the id ingest now gives it, before the dedupe runs,
so naps are not taken for copies. Garmin flags only its naps: the night itself is never one.

Copies of one night are the sessions of one (user, provider, external_id) starting within a day of
the newest; a shared id further apart is left alone. Health scores, session aggregates and details
the keeper lacks move onto it from the newest copy that has them; the rest cascade with the deleted
copies. Coverage is refreshed and the deleted copies' days are queued for the rollup. Internal sleep
scores of those days are not recomputed.

Idempotent: a re-run finds nothing. Runs once per instance through data_migration_service.

Usage (inside Docker), with --dry-run to preview without changes:
    docker compose exec app uv run python scripts/data_migrations/dedupe_sleep_by_external_id.py
"""

import argparse
from collections.abc import Sequence
from typing import cast

from sqlalchemy import CursorResult, Row, text
from sqlalchemy.orm import Session

from app.database import engine
from app.integrations.rollup_queue import mark_dirty_days
from app.repositories.data_type_coverage_repository import data_type_coverage_repository
from app.repositories.event_record_repository import local_days
from app.services.data_migration_service import data_migration_service

_BATCH_SIZE = 1_000

_RENAME_GARMIN_NAPS = text("""
    UPDATE event_record e
    SET external_id = e.external_id || '-nap-' || extract(epoch FROM e.start_datetime)::bigint
    FROM data_source ds, sleep_details sd
    WHERE ds.id = e.data_source_id AND sd.record_id = e.id
      AND ds.provider = 'garmin' AND e.category = 'sleep' AND sd.is_nap
      AND e.external_id IS NOT NULL AND e.external_id NOT LIKE '%-nap-%'
""")

_DUPLICATES = text("""
    WITH candidates AS (
        SELECT e.id, e.data_source_id, e.external_id, e.start_datetime, e.end_datetime, e.zone_offset,
               e.created_at, ds.user_id, ds.provider
        FROM event_record e
        JOIN data_source ds ON ds.id = e.data_source_id
        WHERE e.category = 'sleep' AND e.external_id IS NOT NULL
          AND (ds.user_id, ds.provider, e.external_id) IN (
              SELECT d.user_id, d.provider, r.external_id
              FROM event_record r
              JOIN data_source d ON d.id = r.data_source_id
              WHERE r.category = 'sleep' AND r.external_id IS NOT NULL
              GROUP BY d.user_id, d.provider, r.external_id
              HAVING count(*) > 1
          )
    ),
    ranked AS (
        SELECT c.*,
               first_value(c.id) OVER w AS keeper_id,
               first_value(c.start_datetime) OVER w AS keeper_start
        FROM candidates c
        WINDOW w AS (PARTITION BY c.user_id, c.provider, c.external_id ORDER BY c.created_at DESC, c.id DESC)
    )
    SELECT r.id, r.keeper_id, r.data_source_id, r.external_id, r.start_datetime, r.end_datetime, r.zone_offset,
           r.user_id, r.provider
    FROM ranked r
    WHERE r.id <> r.keeper_id AND abs(extract(epoch FROM r.start_datetime - r.keeper_start)) < 86400
    ORDER BY r.keeper_id, r.created_at DESC, r.id DESC
""")

# Copies arrive newest first per keeper, so the newest copy that has a row is the one moved
_PAIRS = "unnest(CAST(:ids AS uuid[]), CAST(:keepers AS uuid[])) WITH ORDINALITY AS p(id, keeper_id, rank)"

_MOVE_SCORES = text(f"""
    UPDATE health_score h SET event_record_id = c.keeper_id
    FROM (
        SELECT DISTINCT ON (p.keeper_id, x.provider, x.category) x.id, p.keeper_id
        FROM {_PAIRS} JOIN health_score x ON x.event_record_id = p.id
        WHERE NOT EXISTS (
            SELECT 1 FROM health_score k
            WHERE k.event_record_id = p.keeper_id AND k.provider = x.provider AND k.category = x.category
        )
        ORDER BY p.keeper_id, x.provider, x.category, p.rank
    ) c
    WHERE h.id = c.id
""")

_MOVE_AGGREGATES = text(f"""
    UPDATE event_record_aggregate a SET record_id = c.keeper_id
    FROM (
        SELECT DISTINCT ON (p.keeper_id, x.series_type_definition_id, x.computed_by) x.id, p.keeper_id
        FROM {_PAIRS} JOIN event_record_aggregate x ON x.record_id = p.id
        WHERE NOT EXISTS (
            SELECT 1 FROM event_record_aggregate k
            WHERE k.record_id = p.keeper_id AND k.series_type_definition_id = x.series_type_definition_id
              AND k.computed_by = x.computed_by
        )
        ORDER BY p.keeper_id, x.series_type_definition_id, x.computed_by, p.rank
    ) c
    WHERE a.id = c.id
""")

_MOVE_DETAILS = text(f"""
    UPDATE sleep_details d SET record_id = c.keeper_id
    FROM (
        SELECT DISTINCT ON (p.keeper_id) p.id, p.keeper_id
        FROM {_PAIRS} JOIN sleep_details x ON x.record_id = p.id
        WHERE NOT EXISTS (SELECT 1 FROM sleep_details k WHERE k.record_id = p.keeper_id)
        ORDER BY p.keeper_id, p.rank
    ) c
    WHERE d.record_id = c.id
""")

_DELETE = text("DELETE FROM event_record WHERE id = ANY(CAST(:ids AS uuid[])) RETURNING id")


def _remove(db: Session, rows: Sequence[Row]) -> int:
    params = {"ids": [row.id for row in rows], "keepers": [row.keeper_id for row in rows]}
    for statement in (_MOVE_SCORES, _MOVE_AGGREGATES, _MOVE_DETAILS):
        db.execute(statement, params)
    deleted = len(db.execute(_DELETE, params).fetchall())
    data_type_coverage_repository.refresh_events(db, {(row.user_id, row.provider, "sleep") for row in rows})
    mark_dirty_days(
        db,
        [
            day
            for row in rows
            for day in local_days(row.data_source_id, row.start_datetime, row.end_datetime, row.zone_offset)
        ],
    )
    db.commit()
    return deleted


def dedupe_sleep(db: Session, *, dry_run: bool) -> int:
    """Commits the nap ids, then after each batch. Returns the number of duplicates found."""
    preview = db.begin_nested()
    renamed = cast(CursorResult, db.execute(_RENAME_GARMIN_NAPS)).rowcount
    print(f"Garmin naps given their own id: {renamed}")
    rows = db.execute(_DUPLICATES).fetchall()
    if dry_run:
        preview.rollback()
    else:
        preview.commit()
        db.commit()

    if not rows:
        print("No duplicate sleeps - nothing to do.")
        return 0

    print(f"Duplicate sleeps to delete: {len(rows)}")
    print(f"\n{'Provider':<10} {'External ID':<38} {'Start':<34} End")
    print("-" * 120)
    for row in rows[:20]:
        print(f"{row.provider:<10} {row.external_id:<38} {row.start_datetime!s:<34} {row.end_datetime}")
    if len(rows) > 20:
        print(f"  ... and {len(rows) - 20} more")

    if dry_run:
        print("\nDry run - no changes made.")
        return len(rows)

    deleted = sum(_remove(db, rows[i : i + _BATCH_SIZE]) for i in range(0, len(rows), _BATCH_SIZE))
    print(f"\nDeleted {deleted} sleep(s).")
    return len(rows)


def _migrate(db: Session, dry_run: bool) -> bool:
    dedupe_sleep(db, dry_run=dry_run)
    return not dry_run


def main(dry_run: bool) -> None:
    with engine.connect() as connection, Session(bind=connection) as db:
        data_migration_service.run(db, "dedupe_sleep_by_external_id", lambda: _migrate(db, dry_run), dry_run=dry_run)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview affected rows without deleting")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
