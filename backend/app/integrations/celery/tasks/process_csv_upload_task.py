from logging import getLogger
from typing import Any
from uuid import UUID

from app.database import SessionLocal
from app.services.cgm_csv.csv_parser import parse_cgm_file
from app.services.timeseries_service import timeseries_service
from celery import shared_task

log = getLogger(__name__)


@shared_task
def process_csv_upload(file_contents: bytes, filename: str, user_id: str) -> dict[str, Any]:
    """Process CGM file (CSV or PDF) and import glucose readings to database.

    Supports Dexcom Clarity CSV, LibreView CSV, and LibreView PDF formats (auto-detected).

    Args:
        file_contents: File contents as bytes
        filename: Original filename (used to detect PDF vs CSV)
        user_id: User ID to associate with the data

    Returns:
        Dict with status, message, and import statistics
    """
    samples, stats = parse_cgm_file(file_contents, filename, UUID(user_id), log)

    with SessionLocal() as db:
        try:
            if samples:
                timeseries_service.bulk_create_samples(db, samples)
                db.commit()

            return {
                "user_id": user_id,
                "status": "success",
                "message": "CGM import completed successfully",
                "stats": {
                    "records_processed": stats.records_processed,
                    "records_skipped": stats.records_skipped,
                    "skip_reasons": stats.skip_reasons,
                    "detected_format": stats.detected_format,
                },
            }

        except Exception as e:
            db.rollback()
            log.exception("Failed to import file %s for user %s", filename, user_id)
            raise e
