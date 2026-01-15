from fastapi import APIRouter, UploadFile

from app.integrations.celery.tasks.poll_sqs_task import poll_sqs_task
from app.integrations.celery.tasks.process_xml_upload_task import process_xml_upload
from app.schemas import PresignedURLRequest, PresignedURLResponse
from app.services import ApiKeyDep, pre_url_service

router = APIRouter()


@router.post("/users/{user_id}/import/apple/xml/s3")
async def import_xml_presigned_url(
    user_id: str,
    request: PresignedURLRequest,
    _api_key: ApiKeyDep,
) -> PresignedURLResponse:
    """Generate presigned URL for XML file upload and trigger processing task."""
    presigned_response = pre_url_service.create_presigned_url(user_id, request)

    poll_sqs_task.delay(expiration_seconds=presigned_response.expires_in, user_id=user_id)

    return presigned_response


@router.post("/users/{user_id}/import/apple/xml/direct")
async def import_xml_file(
    user_id: str,
    file: UploadFile,
    _api_key: ApiKeyDep,
) -> dict[str, str]:
    """Import XML file into the database."""
    file_contents = await file.read()
    filename = file.filename or "upload.xml"

    task = process_xml_upload.delay(file_contents=file_contents, filename=filename, user_id=user_id)

    return {
        "status": "processing",
        "task_id": task.id,
        "user_id": user_id,
    }
