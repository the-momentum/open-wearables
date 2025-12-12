from fastapi import APIRouter

from app.integrations.celery.tasks.poll_sqs_task import poll_sqs_task
from app.schemas import PresignedURLRequest, PresignedURLResponse
from app.services import ApiKeyDep, pre_url_service

router = APIRouter()


@router.post("/users/{user_id}/import/apple/xml")
async def import_xml(
    user_id: str,
    request: PresignedURLRequest,
    _api_key: ApiKeyDep,
) -> PresignedURLResponse:
    """Generate presigned URL for XML file upload and trigger processing task."""
    presigned_response = pre_url_service.create_presigned_url(user_id, request)

    poll_sqs_task.delay(presigned_response.expires_in)

    return presigned_response
