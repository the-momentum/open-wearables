#!/usr/bin/env python3
"""Delete duplicate workouts that share one data source and external_id, keeping the newest copy.

Workouts were matched only on their exact timestamps, so a provider re-delivering one with revised
times (e.g. Whoop trimming a workout after the webhook) stored a second row (#1607). The newest copy
holds the provider's current version, the same rule ingest now applies. Health scores the keeper
lacks move onto it; details and aggregates of the deleted copies cascade.

Usage (inside Docker):
    docker compose exec app uv run python scripts/data_migrations/dedupe_workouts_by_external_id.py --dry-run
    docker compose exec app uv run python scripts/data_migrations/dedupe_workouts_by_external_id.py
"""

import argparse

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import engine
from app.integrations.rollup_queue import mark_dirty_days
from app.repositories.data_type_coverage_repository import data_type_coverage_repository
from app.repositories.event_record_repository import local_days
from app.services.data_migration_service import data_migration_service

_DUPLICATES = """
    WITH ranked AS (
        SELECT er.id, er.data_source_id, er.external_id, er.start_datetime, er.end_datetime, er.zone_offset,
               first_value(er.id) OVER (
                   PARTITION BY er.data_source_id, er.external_id ORDER BY er.created_at DESC, er.id
               ) AS keeper_id
        FROM event_record er
        WHERE er.category = 'workout'
          AND er.external_id IS NOT NULL
          AND (er.data_source_id, er.external_id) IN (
              SELECT data_source_id, external_id
              FROM event_record
              WHERE category = 'workout' AND external_id IS NOT NULL
              GROUP BY data_source_id, external_id
              HAVING count(*) > 1
          )
    )
    SELECT * FROM ranked WHERE id <> keeper_id
"""

_SELECT = text(f"""
    WITH dups AS ({_DUPLICATES})
    SELECT d.id, d.keeper_id, d.data_source_id, d.external_id, d.start_datetime, d.end_datetime, d.zone_offset,
           ds.user_id, ds.provider
    FROM dups d
    JOIN data_source ds ON ds.id = d.data_source_id
    ORDER BY ds.provider, d.start_datetime DESC
""")

# One score per (keeper, provider, category), and only where the keeper has none
_MOVE_SCORES = text(f"""
    WITH dups AS ({_DUPLICATES}),
    movable AS (
        SELECT DISTINCT ON (d.keeper_id, hs.provider, hs.category) hs.id, d.keeper_id
        FROM health_score hs
        JOIN dups d ON d.id = hs.event_record_id
        WHERE NOT EXISTS (
            SELECT 1 FROM health_score k
            WHERE k.event_record_id = d.keeper_id AND k.provider = hs.provider AND k.category = hs.category
        )
        ORDER BY d.keeper_id, hs.provider, hs.category, hs.created_at DESC
    )
    UPDATE health_score hs SET event_record_id = m.keeper_id FROM movable m WHERE hs.id = m.id
""")

_DELETE = text(f"""
    WITH dups AS ({_DUPLICATES})
    DELETE FROM event_record er USING dups d WHERE er.id = d.id
""")


def dedupe_workouts(db: Session, *, dry_run: bool) -> int:
    """Does not commit; the caller owns the transaction. Returns the number of duplicates found."""
    rows = db.execute(_SELECT).fetchall()
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

    moved = db.execute(_MOVE_SCORES).rowcount  # ty: ignore[unresolved-attribute]
    deleted = db.execute(_DELETE).rowcount  # ty: ignore[unresolved-attribute]
    data_type_coverage_repository.refresh_events(db, {(row.user_id, row.provider, "workout") for row in rows})
    mark_dirty_days(
        db,
        [
            day
            for row in rows
            for day in local_days(row.data_source_id, row.start_datetime, row.end_datetime, row.zone_offset)
        ],
    )
    print(f"\nMoved {moved} health score(s), deleted {deleted} workout(s).")
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
