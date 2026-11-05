#!/usr/bin/env python3
"""Queue the flagging of the naps already stored for providers that don't report them (#938).

Their sleep was all stored with is_nap false, so a daytime nap counted as the day's main sleep. Writes now flag
naps with the rule in app.services.sleep_naps; the classify_sleep_naps Celery task applies it to the sleep stored
before and rebuilds the internal sleep scores of the days whose flags change, a few minutes at a time, so startup
does not wait for it. Queued at every startup until the task records it as done (data_migration).

--dry-run counts the flags that would change, here and without writing.

Usage (inside Docker):
    docker compose exec app uv run python scripts/data_migrations/classify_sleep_naps.py --dry-run
    docker compose exec app uv run python scripts/data_migrations/classify_sleep_naps.py
"""

import argparse

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.integrations.celery.core import create_celery
from app.integrations.celery.tasks.classify_sleep_naps_task import MIGRATION, classify_sleep_naps
from app.models import DataSource
from app.repositories.data_migration_repository import DataMigrationRepository
from app.repositories.data_source_repository import DataSourceRepository
from app.services.sleep_naps import NAP_INFERRED_PROVIDERS, reclassify_naps


def count_nap_changes(db: Session) -> int:
    """The nap flags the task would change; writes nothing."""
    sources = DataSourceRepository(DataSource)
    changed, after = 0, None
    while batch := sources.sleep_sources(db, NAP_INFERRED_PROVIDERS, after, 100):
        for source_id, _ in batch:
            changed += len(reclassify_naps(db, source_id, None, dry_run=True))
            after = source_id
    return changed


def main(dry_run: bool) -> None:
    with SessionLocal() as db:
        if dry_run:
            print(
                f"Would change the nap flag of {count_nap_changes(db)} sleep session(s).\n\nDry run: no changes made."
            )
            return
        if DataMigrationRepository().is_completed(db, MIGRATION):
            print(f"{MIGRATION}: already completed, skipping.")
            return
    # Outside the app, the Celery app is not configured yet: without this .delay() goes to the default broker.
    create_celery()
    classify_sleep_naps.delay()
    print(f"{MIGRATION}: queued.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Count the flags that would change without writing")
    main(dry_run=parser.parse_args().dry_run)
