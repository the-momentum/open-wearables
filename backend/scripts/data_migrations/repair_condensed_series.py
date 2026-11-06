#!/usr/bin/env python3
"""Queue the repair of the HealthKit condensed series stored before the SDK import dropped them (#1983).

The why and the decision rules are in app/services/sdk/condensed_series.py. The repair_condensed_series Celery task
applies them to the rows with a window (stored since #1931) inside the user's Apple workouts older than
MIN_CONDENSED_AGE: it restores the original a series overwrote, or deletes the series, and queues the changed days
for the rollup, a few minutes at a time, so startup does not wait for it. Queued at every startup until the task
records it as done (data_migration).

--dry-run counts the rows the repair would change, here and without writing.

Known limits: a series stays when the user's workouts never reached OW, when it covers only part of its stored
originals or, for heart rate, only other series, or when an old pod stores it during a rolling deploy after the run;
webhooks already sent are not retracted.

Usage (inside Docker):
    docker compose exec app uv run python scripts/data_migrations/repair_condensed_series.py --dry-run
    docker compose exec app uv run python scripts/data_migrations/repair_condensed_series.py
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
from typing import get_args

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.integrations.celery.core import create_celery
from app.integrations.celery.tasks.repair_condensed_series_task import (
    MIGRATION,
    bound_statements,
    repair_condensed_series,
)
from app.models import DataSource
from app.repositories.data_migration_repository import DataMigrationRepository
from app.repositories.data_source_repository import DataSourceRepository
from app.services.sdk.condensed_series import MIN_CONDENSED_AGE, Repair, repair_source


def count_repairs(db: Session, now: datetime | None = None) -> Counter[tuple[str, Repair]]:
    """The rows the task would repair, by type and action; writes nothing."""
    before = (now or datetime.now(timezone.utc)) - MIN_CONDENSED_AGE
    sources = DataSourceRepository(DataSource)
    by_type: Counter[tuple[str, Repair]] = Counter()
    after = None
    while batch := sources.apple_app_sources(db, after, 100):
        for source_id, user_id, app_id in batch:
            by_type.update(repair_source(db, source_id, user_id, app_id, before, dry_run=True))
            after = source_id
    return by_type


def _print_dry_run(by_type: Counter[tuple[str, Repair]]) -> None:
    done: Counter[str] = Counter()
    for (_, action), rows in by_type.items():
        done[action] += rows
    for type_name in sorted({name for name, _ in by_type}):
        print(f"  {type_name}: " + ", ".join(f"{by_type[(type_name, a)]} {a}" for a in get_args(Repair)))
    print(
        f"Would repair condensed series: {done['restored']} restored, {done['deleted']} deleted; "
        f"{done['kept']} left as they are.\n\nDry run: no changes made."
    )


def main(dry_run: bool) -> None:
    with SessionLocal() as db:
        if dry_run:
            bound_statements(db)
            _print_dry_run(count_repairs(db))
            return
        if DataMigrationRepository().is_completed(db, MIGRATION):
            print(f"{MIGRATION}: already completed, skipping.")
            return
    # Outside the app, the Celery app is not configured yet: without this .delay() goes to the default broker.
    create_celery()
    repair_condensed_series.delay()
    print(f"{MIGRATION}: queued.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Count the rows that would change without writing")
    main(dry_run=parser.parse_args().dry_run)
