import uuid
from logging import getLogger

from fastapi import APIRouter, HTTPException, status

from app.integrations.celery.tasks.process_apple_upload_task import process_apple_upload
from app.schemas import AppleHealthDataRequest, UploadDataResponse
from app.utils.auth import SDKAuthDep
from app.utils.structured_logging import log_structured

router = APIRouter()
logger = getLogger(__name__)


@router.post("/sdk/users/{user_id}/sync/apple")
async def sync_sdk_data(
    user_id: str,
    body: AppleHealthDataRequest,
    auth: SDKAuthDep,
) -> UploadDataResponse:
    """Import Apple HealthKit data asynchronously via Celery.

    Accepts health data exported from Apple HealthKit in the standard format:
    - **records**: Time-series measurements (heart rate, steps, distance, etc.)
    - **sleep**: Sleep phase records (in bed, awake, light, deep, REM)
    - **workouts**: Exercise/workout sessions with statistics

    The data is queued for asynchronous processing. All fields are optional - you can send
    any combination of records, sleep, and workouts.

    **Authentication:**
    - SDK user token (Bearer token) - token must match the user_id in the path
    - API key (X-Open-Wearables-API-Key header) - can be used for any user

    **Response:**
    Returns immediately with status 202 (Accepted) indicating the task was queued.
    The actual import happens in the background via Celery.
    """
    if auth.auth_type == "sdk_token" and (not auth.user_id or str(auth.user_id) != user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token does not match user_id",
        )

    # Generate unique batch ID for tracking
    batch_id = str(uuid.uuid4())

    # Extract and count data types from payload
    data = body.data
    records_count = len(data.records)
    workouts_count = len(data.workouts)
    sleep_count = len(data.sleep)

    # Log initial batch receipt with counts
    log_structured(
        logger,
        "info",
        "Apple sync batch received",
        action="apple_sdk_batch_received",
        batch_id=batch_id,
        user_id=user_id,
        records_count=records_count,
        workouts_count=workouts_count,
        sleep_count=sleep_count,
        total_items=records_count + workouts_count + sleep_count,
        source="healthion",
    )

    content_str = body.model_dump_json()

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
