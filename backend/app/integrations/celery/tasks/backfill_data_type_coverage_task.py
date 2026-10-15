"""Fills data_type_coverage from the data held before it existed, once per instance.

Scheduled by beat rather than run at startup: on a large instance it takes minutes, which
must not hold the app back from starting. Until it completes, coverage starts at the first
write after the deploy. Each tick after that ends on the data_migration check.
"""

from logging import getLogger

from celery import shared_task
from sqlalchemy.orm import Session

from app.database import engine
from app.repositories.data_type_coverage_repository import data_type_coverage_repository
from app.services.data_migration_service import data_migration_service

logger = getLogger(__name__)

MIGRATION_NAME = "backfill_data_type_coverage"


def run_backfill(*, dry_run: bool = False) -> None:
    # One connection for the whole run: the data_migration lock belongs to it.
    with engine.connect() as connection, Session(bind=connection) as db:

        def migrate() -> bool:
            found = data_type_coverage_repository.backfill_from_held_data(db, dry_run=dry_run)
            verb = "Would record" if dry_run else "Recorded"
            for kind, spans in found.items():
                print(f"{verb} {spans} {kind} span(s).")
            return not dry_run

        data_migration_service.run(db, MIGRATION_NAME, migrate, dry_run=dry_run)


# TODO: Remove this, with its beat entry, after ~2027-03-01 once all deployments have migrated.
@shared_task(
    name="app.integrations.celery.tasks.backfill_data_type_coverage_task.backfill_data_type_coverage",
    ignore_result=True,
)
def backfill_data_type_coverage() -> None:
    run_backfill()
