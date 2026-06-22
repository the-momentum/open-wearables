import os
import tempfile
from logging import getLogger
from pathlib import Path

from celery import shared_task
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services import event_record_service
from app.services.apple.apple_xml.aws_service import get_s3_client
from app.services.apple.apple_xml.xml_service import XMLService
from app.services.apple.healthkit.sleep_service import handle_sleep_data
from app.services.timeseries_service import timeseries_service
from app.services.user_service import user_service
from app.utils.exceptions import ResourceNotFoundError
from app.utils.sentry_helpers import log_and_capture_error

logger = getLogger(__name__)


@shared_task
def process_aws_upload(bucket_name: str, object_key: str, user_id: str) -> dict[str, str]:
    """
    Process XML file uploaded to S3 and import to Postgres database.

    Args:
        bucket_name: S3 bucket name
        object_key: S3 object key (path)
    """

    s3_client = get_s3_client()
    if not s3_client:
        err = RuntimeError("S3 client not configured — cannot process AWS upload")
        log_and_capture_error(
            err,
            logger,
            "S3 client unavailable in process_aws_upload task",
            extra={"bucket_name": bucket_name, "object_key": object_key, "user_id": user_id},
        )
        raise err

    db = SessionLocal()
    temp_xml_file = None

    try:
        temp_dir = tempfile.gettempdir()
        temp_xml_file = os.path.join(temp_dir, f"temp_import_{object_key.split('/')[-1]}")

        # Validate that the user exists before processing
        try:
            _ = user_service.get(db, user_id, raise_404=True)
        except ResourceNotFoundError as e:
            log_and_capture_error(
                e,
                logger,
                "Skipping import for non-existent user",
                extra={"user_id": user_id},
            )
            return {
                "status": "skipped",
                "reason": str(e),
            }

        s3_client.download_file(bucket_name, object_key, temp_xml_file)

        try:
            _import_xml_data(temp_xml_file, user_id)
        except Exception as e:
            raise e

        return {
            "bucket": bucket_name,
            "input_key": object_key,
            "user_id": user_id,
            "status": "success",
            "message": "Import completed successfully",
        }

    finally:
        if temp_xml_file and os.path.exists(temp_xml_file):
            os.remove(temp_xml_file)
        db.close()


def _import_xml_data(xml_path: str, user_id: str) -> None:
    """
    Parse XML file and import data to database.

    Uses a fresh session for each operation type (time series, workouts, sleep)
    to avoid session state conflicts from after_commit webhook listeners.
    """
    xml_service = XMLService(Path(xml_path), getLogger(__name__))

    for time_series_records, workouts, sync_request in xml_service.parse_xml(user_id):
        if workouts:
            for record, detail in workouts:
                workout_db = SessionLocal()
                try:
                    created_record = event_record_service.create(workout_db, record)
                    detail_for_record = detail.model_copy(update={"record_id": created_record.id})
                    event_record_service.create_detail(workout_db, detail_for_record)
                except Exception as e:
                    logger.warning("Failed to save workout record: %s - skipping", e)
                finally:
                    workout_db.close()

        if time_series_records:
            ts_db = SessionLocal()
            try:
                timeseries_service.bulk_create_samples(ts_db, time_series_records)
                ts_db.commit()
            finally:
                ts_db.close()

        if sync_request and sync_request.data.sleep:
            sleep_db = SessionLocal()
            try:
                handle_sleep_data(sleep_db, sync_request, user_id)
            finally:
                sleep_db.close()
