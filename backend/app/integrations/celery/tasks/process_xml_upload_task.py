import os
import tempfile
from logging import getLogger
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.schemas.apple.apple_xml.stats import XMLParseStats
from app.services import event_record_service
from app.services.apple.apple_xml.xml_service import XMLService
from app.services.timeseries_service import timeseries_service
from app.utils.sentry_helpers import log_and_capture_error
from app.utils.structured_logging import log_structured
from celery import shared_task

log = getLogger(__name__)


@shared_task
def process_xml_upload(file_contents: bytes, filename: str, user_id: str) -> dict[str, Any]:
    """
    Process XML file and import to Postgres database.

    Args:
        file_contents: XML file contents as bytes
        filename: Original filename
        user_id: User ID to associate with the data

    Returns:
        Dict with status, message, and import statistics
    """
    temp_xml_file = None

    with SessionLocal() as db:
        try:
            temp_dir = tempfile.gettempdir()
            temp_xml_file = os.path.join(temp_dir, f"temp_import_{filename}")

            with open(temp_xml_file, "wb") as f:
                f.write(file_contents)

            stats = _import_xml_data(db, temp_xml_file, user_id)

            return {
                "user_id": user_id,
                "status": "success",
                "message": "Import completed successfully",
                "stats": {
                    "records_processed": stats.records_processed,
                    "records_skipped": stats.records_skipped,
                    "workouts_processed": stats.workouts_processed,
                    "workouts_skipped": stats.workouts_skipped,
                    "skip_reasons": stats.skip_reasons,
                },
            }

        except Exception as e:
            db.rollback()
            log_structured(
                log,
                "error",
                "Failed to import XML file %s for user %s",
                filename,
                user_id,
            )
            log_and_capture_error(
                e,
                log,
                "Failed to import XML file %s for user %s",
                filename,
                user_id,
                extra={"filename": filename, "user_id": user_id},
            )
            raise e

        finally:
            if temp_xml_file and os.path.exists(temp_xml_file):
                os.remove(temp_xml_file)


def _import_xml_data(db: Session, xml_path: str, user_id: str) -> XMLParseStats:
    """
    Parse XML file and import data to database using XMLService.

    Args:
        db: Database session
        xml_path: Path to the XML file
        user_id: User ID to associate with the data

    Returns:
        XMLParseStats with parsing statistics
    """
    xml_service = XMLService(Path(xml_path), log)

    for time_series_records, workouts in xml_service.parse_xml(user_id):
        for record, detail in workouts:
            try:
                created_record = event_record_service.create(db, record)
                detail_for_record = detail.model_copy(update={"record_id": created_record.id})
                event_record_service.create_detail(db, detail_for_record)
            except Exception as e:
                log_structured(
                    log,
                    "warning",
                    "Failed to save workout record %s: %s - skipping",
                    record.type if hasattr(record, "type") else "unknown",
                    str(e),
                )
                log_and_capture_error(
                    e,
                    log,
                    f"Failed to save workout record %s: %s - skipping",
                    extra={"record_type": record.type if hasattr(record, "type") else "unknown", "user_id": user_id},
                )
                xml_service.stats.workout_skip(f"db_error:{type(e).__name__}")

        if time_series_records:
            timeseries_service.bulk_create_samples(db, time_series_records)
            db.commit()

    return xml_service.stats
