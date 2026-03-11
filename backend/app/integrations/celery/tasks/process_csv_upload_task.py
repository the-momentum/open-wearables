from logging import getLogger
from typing import Any
from uuid import UUID

from app.database import SessionLocal
from app.services.cgm_csv.csv_parser import parse_cgm_csv
from app.services.timeseries_service import timeseries_service
from celery import shared_task

log = getLogger(__name__)


@shared_task
def process_csv_upload(file_contents: bytes, filename: str, user_id: str) -> dict[str, Any]:
    """Process CGM CSV file and import glucose readings to database.

    Supports Dexcom Clarity and LibreView CSV formats (auto-detected).

    Args:
        file_contents: CSV file contents as bytes
        filename: Original filename
        user_id: User ID to associate with the data

    Returns:
        Dict with status, message, and import statistics
    """
    # Decode CSV bytes to string with encoding fallback chain
    csv_content = _decode_csv(file_contents)

    samples, stats = parse_cgm_csv(csv_content, UUID(user_id), log)

    with SessionLocal() as db:
        try:
            if samples:
                timeseries_service.bulk_create_samples(db, samples)
                db.commit()

            return {
                "user_id": user_id,
                "status": "success",
                "message": "CGM CSV import completed successfully",
                "stats": {
                    "records_processed": stats.records_processed,
                    "records_skipped": stats.records_skipped,
                    "skip_reasons": stats.skip_reasons,
                    "detected_format": stats.detected_format,
                },
            }

        except Exception as e:
            db.rollback()
            log.exception("Failed to import CSV file %s for user %s", filename, user_id)
            raise e


def _decode_csv(file_contents: bytes) -> str:
    """Decode CSV bytes with encoding fallback: UTF-8 → UTF-8-SIG → Latin-1."""
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return file_contents.decode(encoding)
        except (UnicodeDecodeError, ValueError):
            continue
    raise ValueError("Unable to decode CSV file with supported encodings (UTF-8, UTF-8-SIG, Latin-1)")
