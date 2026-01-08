from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status

from app.integrations.celery.tasks.poll_sqs_task import poll_sqs_task
from app.integrations.celery.tasks.process_apple_upload_task import process_apple_upload
from app.schemas import PresignedURLRequest, PresignedURLResponse, UploadDataResponse
from app.services import ApiKeyDep, pre_url_service

router = APIRouter()


async def get_content_type(request: Request) -> tuple[str, str]:
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type:
        form = await request.form()
        file = form.get("file")
        if not file:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No file found")

        if isinstance(file, UploadFile):
            content_bytes = await file.read()
            content_str = content_bytes.decode("utf-8")
        else:
            content_str = str(file)
    else:
        body = await request.body()
        content_str = body.decode("utf-8")

    return content_str, content_type


@router.post("/users/{user_id}/import/apple/auto-health-export")
async def import_data_auto_health_export(
    user_id: str,
    request: Request,
    _api_key: ApiKeyDep,
    content: Annotated[tuple[str, str], Depends(get_content_type)],
) -> UploadDataResponse:
    """Import health data from file upload or JSON asynchronously via Celery."""
    content_str, content_type = content[0], content[1]
    
    # Queue the import task in Celery with auto-health-export source
    process_apple_upload.delay(content_str, content_type, user_id, "auto-health-export")
    
    return UploadDataResponse(
        status_code=202,
        response="Import task queued successfully"
    )


@router.post("/users/{user_id}/import/apple/healthion")
async def import_data_healthion(
    user_id: str,
    request: Request,
    _api_key: ApiKeyDep,
    content: Annotated[tuple[str, str], Depends(get_content_type)],
) -> UploadDataResponse:
    """Import health data from file upload or JSON asynchronously via Celery."""
    content_str, content_type = content[0], content[1]
    
    # Queue the import task in Celery with healthion source
    process_apple_upload.delay(content_str, content_type, user_id, "healthion")
    
    return UploadDataResponse(
        status_code=202,
        response="Import task queued successfully"
    )


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
