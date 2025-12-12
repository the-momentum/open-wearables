import os
import tempfile
from logging import getLogger
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services import event_record_service, time_series_service, user_service
from app.services.apple.apple_xml.aws_service import s3_client
from app.services.apple.apple_xml.xml_service import XMLService
from celery import shared_task


@shared_task
def process_uploaded_file(bucket_name: str, object_key: str) -> dict[str, str]:
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

            user_id_str = object_key.split("/")[-3]
            try:
                user_id = UUID(user_id_str)
            except ValueError as e:
                raise ValueError(f"Invalid user_id format in object key: {user_id_str}") from e

            # Validate that the user exists before processing
            user = user_service.get(db, user_id, raise_404=False)
            if user is None:
                raise ValueError(f"User with id {user_id} does not exist in the database")

            s3_client.download_file(bucket_name, object_key, temp_xml_file)

            try:
                _import_xml_data(db, temp_xml_file, user_id_str)
                db.commit()
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
            time_series_service.bulk_create_samples(db, time_series_records)
