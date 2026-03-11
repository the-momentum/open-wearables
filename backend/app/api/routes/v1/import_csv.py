from fastapi import APIRouter, UploadFile

from app.integrations.celery.tasks.process_csv_upload_task import process_csv_upload
from app.services import ApiKeyDep

router = APIRouter()


@router.post("/users/{user_id}/import/cgm/csv")
async def import_csv_file(
    user_id: str,
    file: UploadFile,
    _api_key: ApiKeyDep,
) -> dict[str, str]:
    """Import CGM CSV file (Dexcom Clarity or LibreView) into the database."""
    file_contents = await file.read()
    filename = file.filename or "upload.csv"

    task = process_csv_upload.delay(file_contents=file_contents, filename=filename, user_id=user_id)

    return {
        "status": "processing",
        "task_id": task.id,
        "user_id": user_id,
    }
