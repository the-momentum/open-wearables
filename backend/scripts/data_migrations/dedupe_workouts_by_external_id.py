#!/usr/bin/env python3
"""Delete duplicate workouts that share one data source and external_id and overlap in time, keeping the newest.

Workouts were matched only on their exact timestamps, so a provider re-delivering one with revised
times (e.g. Whoop trimming a workout after the webhook) stored a second row (#1607). The newest copy
holds the provider's current version, the same rule ingest now applies.

Copies must also overlap in time: an id shared by workouts far apart is not an id. Suunto stored the
detail endpoint's workoutId, which is always 0, so every Suunto workout of a source shares "0".
Overlapping copies form one cluster per (data source, external_id); the newest copy of each cluster
is kept. Health scores, session aggregates and details the keeper lacks move onto it from the newest
copy that has them; the rest cascade with the deleted copies. Coverage is refreshed and the deleted
copies' days are queued for the rollup.

The clusters are found in one pass over the workouts with a shared external_id, then deleted by
primary key in committed batches. Idempotent: a re-run finds nothing. Runs once per instance
through data_migration_service.

Usage (inside Docker), with --dry-run to preview without changes:
    docker compose exec app uv run python scripts/data_migrations/dedupe_workouts_by_external_id.py
"""

import argparse
from collections.abc import Sequence

from sqlalchemy import Row, text
from sqlalchemy.orm import Session

from app.database import engine
from app.integrations.rollup_queue import mark_dirty_days
from app.repositories.data_type_coverage_repository import data_type_coverage_repository
from app.repositories.event_record_repository import local_days
from app.services.data_migration_service import data_migration_service

_BATCH_SIZE = 1_000

_DUPLICATES = text("""
    WITH candidates AS (
        SELECT e.id, e.data_source_id, e.external_id, e.start_datetime, e.end_datetime, e.zone_offset, e.created_at
        FROM event_record e
        WHERE e.category = 'workout' AND e.external_id IS NOT NULL
          AND (e.data_source_id, e.external_id) IN (
              SELECT data_source_id, external_id
              FROM event_record
              WHERE category = 'workout' AND external_id IS NOT NULL
              GROUP BY data_source_id, external_id
              HAVING count(*) > 1
          )
    ),
    ordered AS (
        SELECT c.*, max(c.end_datetime) OVER (
            PARTITION BY c.data_source_id, c.external_id ORDER BY c.start_datetime, c.id
            ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
        ) AS previous_end
        FROM candidates c
    ),
    clustered AS (
        SELECT o.*, sum(CASE WHEN o.previous_end IS NULL OR o.start_datetime >= o.previous_end THEN 1 ELSE 0 END)
            OVER (PARTITION BY o.data_source_id, o.external_id ORDER BY o.start_datetime, o.id) AS cluster
        FROM ordered o
    ),
    ranked AS (
        SELECT cl.*, first_value(cl.id) OVER (
            PARTITION BY cl.data_source_id, cl.external_id, cl.cluster ORDER BY cl.created_at DESC, cl.id DESC
        ) AS keeper_id
        FROM clustered cl
    )
    SELECT r.id, r.keeper_id, r.data_source_id, r.external_id, r.start_datetime, r.end_datetime, r.zone_offset,
           ds.user_id, ds.provider
    FROM ranked r
    JOIN data_source ds ON ds.id = r.data_source_id
    WHERE r.id <> r.keeper_id
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
    UPDATE workout_details d SET record_id = c.keeper_id
    FROM (
        SELECT DISTINCT ON (p.keeper_id) p.id, p.keeper_id
        FROM {_PAIRS} JOIN workout_details x ON x.record_id = p.id
        WHERE NOT EXISTS (SELECT 1 FROM workout_details k WHERE k.record_id = p.keeper_id)
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
    data_type_coverage_repository.refresh_events(db, {(row.user_id, row.provider, "workout") for row in rows})
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


def dedupe_workouts(db: Session, *, dry_run: bool) -> int:
    """Commits after each batch. Returns the number of duplicates found."""
    rows = db.execute(_DUPLICATES).fetchall()
    if not rows:
        print("No duplicate workouts - nothing to do.")
        return 0

    print(f"Duplicate workouts to delete: {len(rows)}")
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
    print(f"\nDeleted {deleted} workout(s).")
    return len(rows)


def _migrate(db: Session, dry_run: bool) -> bool:
    dedupe_workouts(db, dry_run=dry_run)
    return not dry_run


def main(dry_run: bool) -> None:
    with engine.connect() as connection, Session(bind=connection) as db:
        data_migration_service.run(db, "dedupe_workouts_by_external_id", lambda: _migrate(db, dry_run), dry_run=dry_run)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview affected rows without deleting")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
