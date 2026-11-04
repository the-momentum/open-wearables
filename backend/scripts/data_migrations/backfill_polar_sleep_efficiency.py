#!/usr/bin/env python3
"""Set the sleep efficiency of stored Polar nights from their time asleep and time in bed.

Polar reports no sleep efficiency, so stored Polar nights have none. Ingestion now derives it
like Garmin's, time asleep over time in bed, and a re-sync replaces the nights still in Polar's
90-day window; this sets it on the nights stored before, from their stored minutes. Time in bed
is the night's start-to-end window, which is what Polar sleep stores it as. A night without stages
has no time asleep and keeps no efficiency, and a night holding more sleep than its window is left
as it is.

Waits for dedupe_polar_sleep: until that has run, a night without stages re-synced before #1870
may hold its sleep minutes several times. Runs once per instance (data_migration), in one
statement.

Usage (inside Docker):
    docker compose exec app uv run python scripts/data_migrations/backfill_polar_sleep_efficiency.py --dry-run
    docker compose exec app uv run python scripts/data_migrations/backfill_polar_sleep_efficiency.py
"""

import argparse

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import engine
from app.repositories.data_migration_repository import DataMigrationRepository
from app.schemas.enums import ProviderName
from app.services.data_migration_service import data_migration_service

_NIGHTS = """
    ds.provider = :provider
    AND er.category = 'sleep'
    AND sd.sleep_efficiency_score IS NULL
    AND sd.sleep_total_duration_minutes IS NOT NULL
    AND er.duration_seconds > 0
    -- More sleep than the night lasted is no efficiency, and the sleep summary rejects one above 100
    AND sd.sleep_total_duration_minutes * 60 <= er.duration_seconds
"""
_COUNT = text(f"""
    SELECT count(*)
    FROM sleep_details sd
    JOIN event_record er ON er.id = sd.record_id
    JOIN data_source ds ON ds.id = er.data_source_id
    WHERE {_NIGHTS}
""")
_UPDATE = text(f"""
    UPDATE sleep_details sd
    SET sleep_efficiency_score = round(sd.sleep_total_duration_minutes * 60 * 100.0 / er.duration_seconds, 2)
    FROM event_record er
    JOIN data_source ds ON ds.id = er.data_source_id
    WHERE sd.record_id = er.id AND {_NIGHTS}
""")


def backfill_polar_sleep_efficiency(db: Session, *, dry_run: bool) -> int:
    """Does not commit; the caller owns the transaction. Returns the number of nights set."""
    params = {"provider": ProviderName.POLAR.value}
    if dry_run:
        found = db.execute(_COUNT, params).scalar() or 0
        print(f"Would set the efficiency of {found} Polar night(s).\n\nDry run: no changes made.")
        return found
    updated = db.execute(_UPDATE, params).rowcount  # ty: ignore[unresolved-attribute]
    print(f"Set the efficiency of {updated} Polar night(s).")
    return updated


def _migrate(db: Session, dry_run: bool) -> bool:
    if not DataMigrationRepository().is_completed(db, "dedupe_polar_sleep"):
        print("Waiting for dedupe_polar_sleep, which repairs the minutes this reads.")
        return False
    backfill_polar_sleep_efficiency(db, dry_run=dry_run)
    return not dry_run


def main(dry_run: bool) -> None:
    with engine.connect() as connection, Session(bind=connection) as db:
        data_migration_service.run(
            db, "backfill_polar_sleep_efficiency", lambda: _migrate(db, dry_run), dry_run=dry_run
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview affected rows without modifying data")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
