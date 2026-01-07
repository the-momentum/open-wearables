from fastapi import APIRouter
from fastapi import UploadFile

from app.integrations.celery.tasks.poll_sqs_task import poll_sqs_task
from app.schemas import PresignedURLRequest, PresignedURLResponse
from app.services import ApiKeyDep, pre_url_service

router = APIRouter()


@router.post("/users/{user_id}/import/apple/xml/presigned-url")
async def import_xml_presigned_url(
    user_id: str,
    request: PresignedURLRequest,
    _api_key: ApiKeyDep,
) -> PresignedURLResponse:
    """Generate presigned URL for XML file upload and trigger processing task."""
    presigned_response = pre_url_service.create_presigned_url(user_id, request)

    poll_sqs_task.delay(presigned_response.expires_in)

    return presigned_response

@router.post("/users/{user_id}/import/apple/xml")
async def import_xml_file(
    user_id: str,
    request: UploadFile,
    _api_key: ApiKeyDep,
) -> dict[str, str]:
    """Import XML file into the database."""
    return process_xml_upload_task.delay(request, user_id)