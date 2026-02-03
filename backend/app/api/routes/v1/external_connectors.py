import json

from fastapi import APIRouter, HTTPException, status

from app.integrations.celery.tasks.process_apple_upload_task import process_apple_upload
from app.schemas import UploadDataResponse
from app.utils.auth import SDKAuthDep

router = APIRouter()


@router.post("/users/{user_id}/import/apple/auto-health-export")
async def sync_data_auto_health_export(
    user_id: str,
    body: dict,
    auth: SDKAuthDep,
) -> UploadDataResponse:
    """Import health data from JSON body asynchronously via Celery.

    Accepts either SDK user token (Bearer) or API key (X-Open-Wearables-API-Key header).
    """
    if auth.auth_type == "sdk_token" and (not auth.user_id or str(auth.user_id) != user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token does not match user_id",
        )

    content_str = json.dumps(body)

    # Queue the import task in Celery with auto-health-export source
    process_apple_upload.delay(
        content=content_str,
        content_type="application/json",
        user_id=user_id,
        source="auto-health-export",
    )

    return UploadDataResponse(status_code=202, response="Import task queued successfully", user_id=user_id)
