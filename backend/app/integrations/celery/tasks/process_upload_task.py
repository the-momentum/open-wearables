import os
import tempfile
from logging import getLogger
from pathlib import Path

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services import workout_service, workout_statistic_service
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

            user_id = object_key.split("/")[-3]

            s3_client.download_file(bucket_name, object_key, temp_xml_file)

            try:
                _import_xml_data(db, temp_xml_file, user_id)
                db.commit()
            except Exception as e:
                db.rollback()
                raise e

            result = {
                "bucket": bucket_name,
                "input_key": object_key,
                "user_id": user_id,
                "status": "success",
                "message": "Import completed successfully",
            }

            return result

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

    for records, workouts, statistics in xml_service.parse_xml(user_id):
        for record in records:
            workout_statistic_service.create(db, record)
        for workout in workouts:
            workout_service.create(db, workout)
        for stat in statistics:
            workout_statistic_service.create(db, stat)