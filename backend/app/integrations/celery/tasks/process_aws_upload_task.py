import os
import tempfile
from logging import getLogger
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services import event_record_service
from app.services.apple.apple_xml.aws_service import s3_client
from app.services.apple.apple_xml.xml_service import XMLService
from app.services.timeseries_service import timeseries_service
from app.services.user_service import user_service
from celery import shared_task

logger = getLogger(__name__)


@shared_task
def process_aws_upload(bucket_name: str, object_key: str, user_id: str | None = None) -> dict[str, str]:
    """
    Process XML file uploaded to S3 and import to Postgres database.

    Args:
        bucket_name: S3 bucket name
        object_key: S3 object key (path)
    """

    with SessionLocal() as db:
        temp_xml_file = None

        try:
            temp_dir = tempfile.gettempdir()
            temp_xml_file = os.path.join(temp_dir, f"temp_import_{object_key.split('/')[-1]}")

            object_key_parts = object_key.split("/")
            if user_id:
                user_id_str = user_id
            elif len(object_key_parts) >= 3:
                user_id_str = object_key_parts[-3]
            else:
                raise ValueError(f"Cannot determine user_id from object key: {object_key}")
            if user_id and user_id_str != user_id:
                logger.warning(
                    "[process_aws_upload] Provided user_id does not match object key user_id: %s vs %s",
                    user_id,
                    user_id_str,
                )
            try:
                user_uuid = UUID(user_id_str)
            except ValueError as e:
                raise ValueError(f"Invalid user_id format in object key: {user_id_str}") from e

            # Validate that the user exists before processing
            _ = user_service.get(db, user_uuid, raise_404=True)

            s3_client.download_file(bucket_name, object_key, temp_xml_file)

            try:
                _import_xml_data(db, temp_xml_file, user_id_str)
            except Exception as e:
                db.rollback()
                raise e

            return {
                "bucket": bucket_name,
                "input_key": object_key,
                "user_id": user_id_str,
                "status": "success",
                "message": "Import completed successfully",
            }

        finally:
            if temp_xml_file and os.path.exists(temp_xml_file):
                os.remove(temp_xml_file)


def _import_xml_data(db: Session, xml_path: str, user_id: str) -> None:
    """
    Parse XML file and import data to database using XMLExporter.

    Args:
        db: Database session
        xml_path: Path to the XML file
        user_id: User ID to associate with the data
    """
    xml_service = XMLService(Path(xml_path), getLogger(__name__))

    for time_series_records, workouts in xml_service.parse_xml(user_id):
        for record, detail in workouts:
            created_record = event_record_service.create(db, record)
            detail_for_record = detail.model_copy(update={"record_id": created_record.id})
            event_record_service.create_detail(db, detail_for_record)
        if time_series_records:
            timeseries_service.bulk_create_samples(db, time_series_records)
            db.commit()
