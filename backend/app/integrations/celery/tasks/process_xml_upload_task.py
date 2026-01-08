import os
import tempfile
from logging import getLogger
from pathlib import Path

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services import event_record_service
from app.services.apple.apple_xml.xml_service import XMLService
from app.services.timeseries_service import timeseries_service
from celery import shared_task


@shared_task
def process_xml_upload(file_contents: bytes, filename: str, user_id: str) -> dict[str, str]:
    """
    Process XML file and import to Postgres database.

    Args:
        file_contents: XML file contents as bytes
        filename: Original filename
        user_id: User ID to associate with the data
    """
    temp_xml_file = None

    with SessionLocal() as db:
        try:
            temp_dir = tempfile.gettempdir()
            temp_xml_file = os.path.join(temp_dir, f"temp_import_{filename}")

            with open(temp_xml_file, "wb") as f:
                f.write(file_contents)

            _import_xml_data(db, temp_xml_file, user_id)

            return {
                "user_id": user_id,
                "status": "success",
                "message": "Import completed successfully",
            }

        except Exception as e:
            db.rollback()
            raise e

        finally:
            if temp_xml_file and os.path.exists(temp_xml_file):
                os.remove(temp_xml_file)


def _import_xml_data(db: Session, xml_path: str, user_id: str) -> None:
    """
    Parse XML file and import data to database using XMLService.

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
