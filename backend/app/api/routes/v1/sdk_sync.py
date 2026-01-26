import json

from fastapi import APIRouter, HTTPException, status

from app.integrations.celery.tasks.process_apple_upload_task import process_apple_upload
from app.schemas import UploadDataResponse
from app.utils.auth import SDKAuthDep

router = APIRouter()


@router.post("/sdk/users/{user_id}/sync/apple")
async def sync_sdk_data(
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

    # Queue the import task in Celery with healthion source
    process_apple_upload.delay(
        content=content_str,
        content_type="application/json",
        user_id=user_id,
        source="healthion",
    )

    return UploadDataResponse(status_code=202, response="Import task queued successfully", user_id=user_id)


@router.post("/sdk/users/{user_id}/sync/samsung", tags=["beta"])
async def sync_data_samsung(
    user_id: str,
    request: Request,
    auth: SDKAuthDep,
    content: Annotated[tuple[str, str], Depends(get_content_type)],
) -> UploadDataResponse:
    """Import health data from Samsung SDK.

    **⚠️ BETA / NOT READY:** This endpoint is currently in development.
    It accepts authentication but does not process data yet.

    **⚠️ PATH MAY CHANGE:** The endpoint path may change in future versions.
    Do not rely on this path for production integrations.

    Accepts either SDK user token (Bearer) or API key (X-Open-Wearables-API-Key header).
    Currently returns success without processing data.
    """
    if auth.auth_type == "sdk_token" and (not auth.user_id or str(auth.user_id) != user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token does not match user_id",
        )

    return UploadDataResponse(
        status_code=200, response="Samsung sync endpoint ready (hardcoded - no data processing yet)", user_id=user_id
    )
