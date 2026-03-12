from fastapi import APIRouter, HTTPException, UploadFile

from app.integrations.celery.tasks.process_csv_upload_task import process_csv_upload
from app.services import ApiKeyDep

router = APIRouter()

_ALLOWED_EXTENSIONS = {".csv", ".txt", ".pdf"}
_MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


@router.post("/users/{user_id}/import/cgm/csv")
async def import_csv_file(
    user_id: str,
    file: UploadFile,
    _api_key: ApiKeyDep,
) -> dict[str, str]:
    """Import CGM data file (Dexcom Clarity CSV, LibreView CSV, or LibreView PDF)."""
    filename = file.filename or "upload.csv"

    # Validate file extension
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Accepted: {', '.join(sorted(_ALLOWED_EXTENSIONS))}",
        )

    file_contents = await file.read()

    if len(file_contents) > _MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"File too large. Maximum size is {_MAX_FILE_SIZE // (1024 * 1024)} MB.")

    task = process_csv_upload.delay(file_contents=file_contents, filename=filename, user_id=user_id)

    return {
        "status": "processing",
        "task_id": task.id,
        "user_id": user_id,
    }
