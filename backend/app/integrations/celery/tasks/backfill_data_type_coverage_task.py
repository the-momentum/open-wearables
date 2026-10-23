"""Fills data_type_coverage from the data held before it existed, once per instance.

Scheduled by beat rather than run at startup: on a large instance it takes minutes, which
must not hold the app back from starting. Until it completes, coverage starts at the first
write after the deploy. Each tick after that ends on the data_migration check.
"""

from celery import shared_task
from sqlalchemy.orm import Session

from app.constants.celery_tasks import CeleryTask
from app.database import engine
from app.repositories.data_type_coverage_repository import data_type_coverage_repository
from app.schemas.sync_status import DataTypeKind
from app.services.data_migration_service import data_migration_service
from app.utils.structured_logging import get_logger

logger = get_logger(__name__)

MIGRATION_NAME = "backfill_data_type_coverage"


def run_backfill(*, dry_run: bool = False) -> dict[DataTypeKind, int] | None:
    """Spans recorded (or found) per kind, or None when it already ran or runs elsewhere."""
    found: dict[DataTypeKind, int] | None = None
    # One connection for the whole run: the data_migration lock belongs to it.
    with engine.connect() as connection, Session(bind=connection) as db:

        def migrate() -> bool:
            nonlocal found
            found = data_type_coverage_repository.backfill_from_held_data(db, dry_run=dry_run)
            return not dry_run

        data_migration_service.run(db, MIGRATION_NAME, migrate, dry_run=dry_run)
    return found


# TODO: Remove this, with its beat entry, after ~2027-03-01 once all deployments have migrated.
@shared_task(name=CeleryTask.BACKFILL_DATA_TYPE_COVERAGE, ignore_result=True)
def backfill_data_type_coverage() -> None:
    if found := run_backfill():
        logger.info(
            "Data type coverage backfilled",
            task="backfill_data_type_coverage",
            series_spans=found[DataTypeKind.SERIES],
            event_spans=found[DataTypeKind.EVENT],
        )
