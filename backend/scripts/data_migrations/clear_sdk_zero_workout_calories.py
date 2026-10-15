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

Runs once per instance (``data_migration``): one pass collects the workouts, then committed
batches clear them.

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
# Collected in one pass into a session temp table, so batches cost a key lookup each and not a
# rescan of workout_details; the session must stay on one connection (see main)
_DROP = text("DROP TABLE IF EXISTS sdk_zero_kcal")
_COLLECT = text(f"CREATE TEMP TABLE sdk_zero_kcal AS {_ZEROS}")
_INDEX = text("CREATE INDEX ON sdk_zero_kcal (record_id)")
_NEXT = text("SELECT record_id FROM sdk_zero_kcal ORDER BY record_id LIMIT :batch_size")
_CLEAR = text("UPDATE workout_details SET energy_burned = NULL WHERE record_id = ANY(:ids)")
_FORGET = text("DELETE FROM sdk_zero_kcal WHERE record_id = ANY(:ids)")


def clear_sdk_zero_workout_calories(db: Session, *, dry_run: bool) -> int:
    """Commits per batch, so an interrupted run keeps what it cleared."""
    params = {"providers": sorted(SDK_PROVIDERS)}
    if dry_run:
        found = db.execute(_COUNT, params).scalar() or 0
        print(f"Would clear 0 kcal on {found} SDK workout(s).\n\nDry run — no changes made.")
        return found

    db.execute(_DROP)
    db.execute(_COLLECT, params)
    db.execute(_INDEX)
    db.commit()
    cleared = 0
    while ids := list(db.execute(_NEXT, {"batch_size": _BATCH_SIZE}).scalars()):
        db.execute(_CLEAR, {"ids": ids})
        db.execute(_FORGET, {"ids": ids})
        db.commit()
        cleared += len(ids)
    db.execute(_DROP)
    db.commit()
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
