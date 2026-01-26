import json
import uuid
from logging import getLogger

from fastapi import APIRouter, HTTPException, status

from app.integrations.celery.tasks.process_apple_upload_task import process_apple_upload
from app.schemas import UploadDataResponse
from app.utils.auth import SDKAuthDep
from app.utils.structured_logging import log_structured

router = APIRouter()
logger = getLogger(__name__)


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

    # Generate unique batch ID for tracking
    batch_id = str(uuid.uuid4())

    # Extract and count data types from payload
    data = body.get("data", {})
    records_count = len(data.get("records", []))
    workouts_count = len(data.get("workouts", []))
    sleep_count = len(data.get("sleep", []))

    # Log initial batch receipt with counts
    log_structured(
        logger,
        "info",
        "Apple sync batch received",
        batch_id=batch_id,
        user_id=user_id,
        records_count=records_count,
        workouts_count=workouts_count,
        sleep_count=sleep_count,
        total_items=records_count + workouts_count + sleep_count,
        source="healthion",
    )

    content_str = json.dumps(body)

    # Queue the import task in Celery with batch_id
    process_apple_upload.delay(
        content=content_str,
        content_type="application/json",
        user_id=user_id,
        source="healthion",
        batch_id=batch_id,
    )

    return UploadDataResponse(status_code=202, response="Import task queued successfully", user_id=user_id)


@router.post("/sdk/users/{user_id}/sync/samsung", tags=["beta"])
async def sync_data_samsung(
    user_id: str,
    body: dict,
    auth: SDKAuthDep,
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
