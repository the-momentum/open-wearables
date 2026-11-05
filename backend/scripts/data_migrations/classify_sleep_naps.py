#!/usr/bin/env python3
"""Flag the naps already stored for providers that don't report naps (#938).

Their sleep was all stored with is_nap false, so a daytime nap counted as the day's main sleep. Writes now
flag naps with the rule in app.services.sleep_naps; this applies it to the sleep stored before, one data
source at a time with a commit after each. The internal sleep scores of the days whose flags change are
rebuilt. A failing data source is rolled back and logged, and the run is retried on the next startup.

Runs once per instance (data_migration). --dry-run counts the flags that would change.

Usage (inside Docker):
    docker compose exec app uv run python scripts/data_migrations/classify_sleep_naps.py --dry-run
    docker compose exec app uv run python scripts/data_migrations/classify_sleep_naps.py
"""

import argparse

from sqlalchemy import exists, select, text
from sqlalchemy.orm import Session

from app.database import engine
from app.models import DataSource, EventRecord
from app.schemas.enums import EventCategory
from app.services.data_migration_service import data_migration_service
from app.services.event_record_service import event_record_service
from app.services.sleep_naps import NAP_INFERRED_PROVIDERS, reclassify_naps
from app.utils.structured_logging import get_logger

logger = get_logger(__name__)

# A live sync holding a lock fails the data source instead of stalling startup; the next run retries it
_LOCK_TIMEOUT = text("SET lock_timeout = '10s'")


def classify_sleep_naps(db: Session, *, dry_run: bool) -> int:
    """Returns the number of flags changed (or that would change in a dry run).

    Commits per data source, so an interrupted run keeps the sources it finished.
    """
    has_sleep = exists().where(EventRecord.data_source_id == DataSource.id, EventRecord.category == EventCategory.SLEEP)
    sources = db.execute(
        select(DataSource.id, DataSource.user_id).where(
            DataSource.provider.in_(list(NAP_INFERRED_PROVIDERS)), has_sleep
        )
    ).all()
    changed = 0
    failed = 0
    for source_id, user_id in sources:
        try:
            if dry_run:
                changed += len(reclassify_naps(db, source_id, None, dry_run=True))
                continue
            count = event_record_service.reclassify_sleep_naps(db, user_id, source_id, None)
            db.commit()
            changed += count
        except Exception as exc:
            db.rollback()
            failed += 1
            print(f"Failed to classify the naps of data source {source_id}")
            logger.error("Failed to classify sleep naps", exc_info=exc, data_source_id=str(source_id))
    if dry_run:
        print(f"Would change the nap flag of {changed} sleep session(s).\n\nDry run: no changes made.")
    else:
        print(f"Changed the nap flag of {changed} sleep session(s) in {len(sources)} data source(s).")
    if failed:
        print(f"{failed} data source(s) failed.")
        raise RuntimeError(f"Nap classification failed for {failed} data source(s)")
    return changed


def _migrate(db: Session, dry_run: bool) -> bool:
    classify_sleep_naps(db, dry_run=dry_run)
    return not dry_run


def main(dry_run: bool) -> None:
    with engine.connect() as connection, Session(bind=connection) as db:
        # Committed, so a data source rolled back later doesn't undo it
        db.execute(_LOCK_TIMEOUT)
        db.commit()
        data_migration_service.run(db, "classify_sleep_naps", lambda: _migrate(db, dry_run), dry_run=dry_run)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview affected rows without modifying data")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
