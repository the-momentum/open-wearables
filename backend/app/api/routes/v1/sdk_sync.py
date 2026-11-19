import uuid
from logging import getLogger

from fastapi import APIRouter, HTTPException, Response, status

from app.integrations.celery.dispatch import dispatch, is_inline
from app.integrations.celery.tasks.process_sdk_upload_task import process_sdk_upload
from app.schemas.providers.mobile_sdk import SyncRequest
from app.schemas.responses.upload import UploadDataResponse
from app.services.raw_payload_storage import store_raw_payload
from app.utils.auth import SDKAuthDep
from app.utils.structured_logging import log_structured

router = APIRouter()
logger = getLogger(__name__)


@router.post("/sdk/users/{user_id}/sync", status_code=status.HTTP_202_ACCEPTED)
def sync_sdk_data(
    user_id: str,
    body: SyncRequest,
    auth: SDKAuthDep,
    response: Response,
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
    if provider not in ("apple", "samsung", "google"):
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

    store_raw_payload(
        source="sdk",
        provider=provider,
        payload=content_str,
        user_id=user_id,
        trace_id=batch_id,
    )

    result = dispatch(
        process_sdk_upload,
        content=content_str,
        content_type="application/json",
        user_id=user_id,
        provider=provider,
        batch_id=batch_id,
    )

    if is_inline():
        # Task ran synchronously; surface the real import outcome.
        body_status = _result_status_code(result)
        response.status_code = body_status
        return UploadDataResponse(
            status_code=body_status,
            response=_result_message(result, body_status),
            user_id=user_id,
        )

    return UploadDataResponse(status_code=202, response="Import task queued successfully", user_id=user_id)


def _result_status_code(result: object) -> int:
    if not isinstance(result, dict):
        return status.HTTP_500_INTERNAL_SERVER_ERROR

    try:
        status_code = int(result.get("status_code", status.HTTP_500_INTERNAL_SERVER_ERROR))
    except (TypeError, ValueError):
        return status.HTTP_500_INTERNAL_SERVER_ERROR

    if 100 <= status_code <= 599:
        return status_code

    return status.HTTP_500_INTERNAL_SERVER_ERROR


def _result_message(result: object, status_code: int) -> str:
    if not isinstance(result, dict):
        return "Import failed: task returned an invalid result"

    message = result.get("response") or result.get("message")
    if message:
        return str(message)

    if 200 <= status_code < 300:
        return "Import completed"

    return "Import failed"
