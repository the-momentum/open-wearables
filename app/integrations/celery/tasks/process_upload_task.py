import os
import tempfile
from pathlib import Path
from decimal import Decimal
from uuid import UUID, uuid4  

from celery import shared_task
import pandas as pd
from sqlalchemy.orm import Session

from app.services.apple.apple_xml.aws_service import s3_client
from app.services.apple.apple_xml.xml_service import XMLService
from app.services import hk_workout_service, hk_workout_statistic_service
from app.schemas import HKWorkoutCreate, HKWorkoutStatisticCreate, HKRecordCreate
from app.services import hk_record_service
from app.database import SessionLocal


@shared_task
def process_uploaded_file(bucket_name: str, object_key: str, user_id: str):
    """
    Process XML file uploaded to S3 and import to Postgres database.

    Args:
        bucket_name: S3 bucket name
        object_key: S3 object key (path)
        user_id: User ID to associate with imported data (optional, extracted from object_key if not provided)
    """
    db = SessionLocal()
    
    temp_xml_file = None
    dump_file = None

    try:
        temp_dir = tempfile.gettempdir()
        temp_xml_file = os.path.join(temp_dir, f"temp_import_{object_key.split('/')[-1]}")

        s3_client.download_file(bucket_name, object_key, temp_xml_file)

        try:
            _import_xml_data(db, temp_xml_file, user_id)
            db.commit()
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()


        result = {
            "bucket": bucket_name,
            "input_key": object_key,
            "user_id": user_id,
            "status": "success",
            "message": "Import completed successfully",
        }

        return result

    except Exception as e:
        result = {
            "bucket": bucket_name,
            "input_key": object_key,
            "user_id": user_id,
            "status": "failed",
            "error": str(e),
        }
        return result

    finally:
        # Clean up temporary files
        if temp_xml_file and os.path.exists(temp_xml_file):
            os.remove(temp_xml_file)
        if dump_file and os.path.exists(dump_file):
            os.remove(dump_file)


def _import_xml_data(db: Session, xml_path: str, user_id: str) -> None:
    """
    Parse XML file and import data to database using XMLExporter.

    Args:
        db: Database session
        xml_path: Path to the XML file
        user_id: User ID to associate with the data
    """
    xml_service = XMLService(Path(xml_path))

    for workouts, statistics in xml_service.parse_xml(user_id):
        for workout_create in workouts:
            hk_workout_service.create(db, workout_create)
        for stat in statistics:
            for stat_create in stat:
                hk_workout_statistic_service.create(db, stat_create)
