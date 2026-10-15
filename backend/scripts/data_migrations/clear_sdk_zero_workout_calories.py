#!/usr/bin/env python3
"""Clear the 0 kcal that SDK and Apple XML imports stored for workouts that reported no calories.

Both importers started the workout's ``energy_burned`` at 0 and only added the energy
statistics they found, so a workout without one was saved as 0 kcal instead of unset. Health
Connect never sends calories in a session's statistics, so every one of its workouts got the
0; Apple and Samsung workouts got it whenever a writer left calories out. The importers now
leave the value unset, and this sets the stored zeros of the mobile SDK providers (``apple``
also holds the XML imports) to NULL. A workout with 0 kcal carries no information, so a zero
a writer did report is cleared too.

Cloud providers never had the bug: their zeros are what the provider reported and stay.

Runs once per instance (``data_migration``), in committed batches.

Usage (inside Docker):
    docker compose exec app uv run python scripts/data_migrations/clear_sdk_zero_workout_calories.py --dry-run
    docker compose exec app uv run python scripts/data_migrations/clear_sdk_zero_workout_calories.py
"""

import argparse

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.constants.sdk_providers import SDK_PROVIDERS
from app.database import engine
from app.services.data_migration_service import data_migration_service

_BATCH_SIZE = 10_000

_ZEROS = """
    SELECT wd.record_id
    FROM workout_details wd
    JOIN event_record e ON e.id = wd.record_id
    JOIN data_source ds ON ds.id = e.data_source_id
    WHERE wd.energy_burned = 0 AND ds.provider = ANY(:providers)
"""
_COUNT = text(f"SELECT count(*) FROM ({_ZEROS}) zeros")
_CLEAR_BATCH = text(f"""
    UPDATE workout_details SET energy_burned = NULL
    WHERE record_id IN ({_ZEROS} LIMIT :batch_size)
""")


def clear_sdk_zero_workout_calories(db: Session, *, dry_run: bool) -> int:
    """Commits per batch, so an interrupted run keeps what it cleared."""
    providers = sorted(SDK_PROVIDERS)
    if dry_run:
        found = db.execute(_COUNT, {"providers": providers}).scalar() or 0
        print(f"Would clear 0 kcal on {found} SDK workout(s).\n\nDry run — no changes made.")
        return found

    cleared = 0
    while True:
        batch = db.execute(_CLEAR_BATCH, {"providers": providers, "batch_size": _BATCH_SIZE}).rowcount  # ty: ignore[unresolved-attribute]
        db.commit()
        cleared += batch
        if batch < _BATCH_SIZE:
            break
    print(f"Cleared 0 kcal on {cleared} SDK workout(s).")
    return cleared


def _migrate(db: Session, dry_run: bool) -> bool:
    clear_sdk_zero_workout_calories(db, dry_run=dry_run)
    return not dry_run


def main(dry_run: bool) -> None:
    with engine.connect() as connection, Session(bind=connection) as db:
        data_migration_service.run(
            db, "clear_sdk_zero_workout_calories", lambda: _migrate(db, dry_run), dry_run=dry_run
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview affected rows without modifying data")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
