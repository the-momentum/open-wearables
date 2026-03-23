from fastapi import APIRouter, UploadFile

from app.integrations.task_dispatcher import RegisteredTask, dispatch_task
from app.schemas import PresignedURLRequest, PresignedURLResponse
from app.services import ApiKeyDep
from app.services.apple.apple_xml.presigned_url_service import presigned_url_service

router = APIRouter()


@router.post("/users/{user_id}/import/apple/xml/s3")
def import_xml_presigned_url(
    user_id: str,
    request: PresignedURLRequest,
    _api_key: ApiKeyDep,
) -> PresignedURLResponse:
    """Generate presigned URL for XML file upload and trigger processing task."""
    presigned_response = presigned_url_service.create_presigned_url(user_id, request)

    dispatch_task(
        RegisteredTask.POLL_SQS_TASK,
        kwargs={
            "expiration_seconds": presigned_response.expires_in,
            "user_id": user_id,
        },
    )

    return presigned_response


@router.post("/users/{user_id}/import/apple/xml/direct")
def import_xml_file(
    user_id: str,
    file: UploadFile,
    _api_key: ApiKeyDep,
) -> dict[str, str]:
    """Import XML file into the database."""
    file_contents = file.file.read()
    filename = file.filename or "upload.xml"

    task = dispatch_task(
        RegisteredTask.PROCESS_XML_UPLOAD,
        kwargs={
            "file_contents": file_contents,
            "filename": filename,
            "user_id": user_id,
        },
    )

    return {
        "status": "processing",
        "task_id": task.id,
        "user_id": user_id,
    }


