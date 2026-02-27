import uuid
from logging import getLogger

from fastapi import APIRouter, HTTPException, status

from app.integrations.celery.tasks.process_sdk_upload_task import process_sdk_upload
from app.schemas import SDKSyncRequest, UploadDataResponse
from app.utils.auth import SDKAuthDep
from app.utils.structured_logging import log_structured

router = APIRouter()
logger = getLogger(__name__)


@router.post("/sdk/users/{user_id}/sync")
async def sync_sdk_data(
    user_id: str,
    body: SDKSyncRequest,
    auth: SDKAuthDep,
) -> UploadDataResponse:
    """Import health data from SDK provider asynchronously via Celery.

    Supports Apple HealthKit and Samsung Health SDK formats (identical payloads):
    ```json
    {
        "provider": "apple",
        "sdkVersion": "1.0.0",
        "syncTimestamp": "2021-01-01T00:00:00Z",
        "data": {
            "records": [...],
            "sleep": [...],
            "workouts": [...]
        }
    }
    ```

    Args:
        user_id: SDK user identifier
        body: Health data payload
        auth: SDK authentication (Bearer token or API key)

    Returns:
        UploadDataResponse with 202 status and task queued message

    Raises:
        HTTPException: 403 if token doesn't match user_id, 400 if provider unsupported
    """
    if auth.auth_type == "sdk_token" and (not auth.user_id or str(auth.user_id) != user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token does not match user_id",
        )

    # Normalize provider name
    provider = body.provider.lower()

    # Validate provider
    if provider not in ("apple", "samsung", "google", "auto-health-export"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider: {provider}. Supported: apple, samsung, google",
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
        f"{provider.capitalize()} sync batch received",
        action=f"{provider}_sdk_batch_received",
        batch_id=batch_id,
        user_id=user_id,
        provider=provider,
        records_count=records_count,
        workouts_count=workouts_count,
        sleep_count=sleep_count,
        total_items=records_count + workouts_count + sleep_count,
    )

    content_str = body.model_dump_json()

    process_sdk_upload.delay(
        content=content_str,
        content_type="application/json",
        user_id=user_id,
        provider=provider,
        batch_id=batch_id,
    )

    return UploadDataResponse(status_code=202, response="Import task queued successfully", user_id=user_id)
