from fastapi import APIRouter, HTTPException, status

from app.integrations.celery.tasks.process_apple_upload_task import process_apple_upload
from app.schemas import AppleHealthDataRequest, UploadDataResponse
from app.utils.auth import SDKAuthDep

router = APIRouter()


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

    # Convert validated schema to JSON string (handles datetime serialization automatically)
    content_str = body.model_dump_json()

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
