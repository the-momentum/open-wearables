"""CSV file import endpoints for workout data migration.

Supports importing workout history from fitness platform CSV exports.
Currently supported formats: RunKeeper (cardioActivities.csv).
"""

from fastapi import APIRouter, HTTPException, UploadFile, status

from app.integrations.celery.tasks.process_csv_import_task import process_csv_import
from app.services import ApiKeyDep
from app.services.csv_import.service import SUPPORTED_FORMATS

router = APIRouter()

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


@router.post("/users/{user_id}/import/csv/{source_format}")
async def import_csv_file(
    user_id: str,
    source_format: str,
    file: UploadFile,
    _api_key: ApiKeyDep,
) -> dict:
    """Import workouts from a CSV file export.

    Upload a CSV file from a supported fitness platform and import
    the workout data into Open Wearables.

    Supported formats:
    - **runkeeper**: Upload the ``cardioActivities.csv`` file from a
      RunKeeper data export.

    The import runs asynchronously. Duplicate workouts (same provider,
    start time, end time) are automatically skipped.
    """
    if source_format not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format: '{source_format}'. Supported: {', '.join(sorted(SUPPORTED_FORMATS))}",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024 * 1024)} MB",
        )

    if not content.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file",
        )

    task = process_csv_import.delay(
        content=content.decode("utf-8-sig"),
        user_id=user_id,
        source_format=source_format,
    )

    return {
        "status": "processing",
        "task_id": task.id,
        "user_id": user_id,
        "source_format": source_format,
    }
