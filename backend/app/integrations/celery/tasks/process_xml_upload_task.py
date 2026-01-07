from logging import getLogger

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services import event_record_service
from app.services.timeseries_service import timeseries_service
from app.services.apple.apple_xml.xml_service import XMLService
from celery import shared_task


@shared_task
def process_xml_upload_task(file: UploadFile, user_id: str) -> dict[str, str]:
    """
    Process XML file and import to Postgres database.

    Args:
        file: Uploaded XML file
    """

    with SessionLocal() as db:
        try:
            _import_xml_data(db, file, user_id)
        except Exception as e:
            db.rollback()
            raise e

        return {
            "user_id": user_id,
            "status": "success",
            "message": "Import completed successfully",
        }


def _import_xml_data(db: Session, file: UploadFile, user_id: str) -> None:
    """
    Parse XML file and import data to database using XMLExporter.

    Args:
        db: Database session
        file: Uploaded XML file
        user_id: User ID to associate with the data
    """
    xml_service = XMLService(file, getLogger(__name__))

    for time_series_records, workouts in xml_service.parse_xml(user_id):
        for record, detail in workouts:
            created_record = event_record_service.create(db, record)
            detail_for_record = detail.model_copy(update={"record_id": created_record.id})
            event_record_service.create_detail(db, detail_for_record)
        if time_series_records:
            timeseries_service.bulk_create_samples(db, time_series_records)
