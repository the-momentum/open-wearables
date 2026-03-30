"""Celery task for processing CSV file imports."""

from logging import getLogger
from uuid import UUID

from app.database import SessionLocal
from app.services.csv_import import csv_import_service
from celery import shared_task

logger = getLogger(__name__)


@shared_task(
    name="app.integrations.celery.tasks.process_csv_import_task.process_csv_import",
    soft_time_limit=300,
    time_limit=360,
    acks_late=True,
    max_retries=2,
    default_retry_delay=30,
)
def process_csv_import(
    content: str,
    user_id: str,
    source_format: str,
) -> dict:
    """Parse a CSV export and import workouts into the database.

    Args:
        content: Raw CSV content as string.
        user_id: User UUID string.
        source_format: CSV format identifier (e.g. "runkeeper").
    """
    with SessionLocal() as db:
        result = csv_import_service.import_csv(
            db_session=db,
            content=content,
            user_id=UUID(user_id),
            source_format=source_format,
        )
        logger.info("CSV import task complete: %s", result)
        return result
