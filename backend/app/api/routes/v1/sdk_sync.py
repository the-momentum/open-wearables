import json
import uuid
from logging import getLogger

from fastapi import APIRouter, HTTPException, status

from app.config import settings
from app.integrations.celery.tasks.process_sdk_upload_task import process_sdk_upload
from app.schemas.providers.mobile_sdk import SyncRequest
from app.schemas.responses.upload import UploadDataResponse
from app.services.raw_payload_storage import put_payload_to_s3, store_raw_payload
from app.utils.api_utils import inline_schema_defs
from app.utils.auth import SDKAuthDep
from app.utils.sentry_helpers import log_and_capture_error
from app.utils.structured_logging import log_structured

router = APIRouter()
logger = getLogger(__name__)


@router.post(
    "/sdk/users/{user_id}/sync",
    status_code=status.HTTP_202_ACCEPTED,
    # body is `dict` at runtime; keep the SyncRequest shape in the OpenAPI docs.
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": inline_schema_defs(SyncRequest.model_json_schema())}},
        }
    },
)
def sync_sdk_data(
    user_id: str,
    body: dict,
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
        HTTPException: 403 if token doesn't match user_id, 400 if provider unsupported.
        Payload validation runs async in the worker, not here.
    """
    if auth.auth_type == "sdk_token" and (not auth.user_id or str(auth.user_id) != user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token does not match user_id",
        )

    # Raw dict, not SyncRequest: schema-validating here would 400 the whole batch on one
    # bad record pre-dispatch. The worker validates and reports failures to Sentry.
    provider = str(body.get("provider") or "").lower()

    # Validate provider (routing decision — needed to select an import service)
    if provider not in ("apple", "samsung", "google"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider: {provider}. Supported: apple, samsung, google",
        )

    # Generate unique batch ID for tracking
    batch_id = str(uuid.uuid4())

    # Extract and count data types from payload (best-effort; structure not yet validated)
    raw_data = body.get("data")
    data = raw_data if isinstance(raw_data, dict) else {}
    records = data.get("records")
    workouts = data.get("workouts")
    sleep = data.get("sleep")
    records_count = len(records) if isinstance(records, list) else 0
    workouts_count = len(workouts) if isinstance(workouts, list) else 0
    sleep_count = len(sleep) if isinstance(sleep, list) else 0

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

    content_str = json.dumps(body)

    offload = settings.sdk_payload_s3_offload
    payload_ref: str | None = None

    if offload:
        payload_ref = put_payload_to_s3(
            source="sdk", provider=provider, payload=content_str, user_id=user_id, trace_id=batch_id
        )
    else:
        store_raw_payload(source="sdk", provider=provider, payload=content_str, user_id=user_id, trace_id=batch_id)

    if offload and payload_ref is None:
        # Fail loudly: falling back to an inline body is what fills the broker until Redis
        # hits maxmemory, and the SDK can retry the upload.
        log_structured(
            logger,
            "error",
            "Failed to persist SDK payload to S3; rejecting batch",
            action="sdk_payload_persist_failed",
            batch_id=batch_id,
            user_id=user_id,
            provider=provider,
        )
        exc = HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to persist payload; please retry.",
        )
        log_and_capture_error(
            exc,
            logger,
            "Failed to persist SDK payload to S3; rejecting batch",
            extra={"batch_id": batch_id, "user_id": user_id, "provider": provider},
        )
        raise exc

    process_sdk_upload.delay(
        content=None if offload else content_str,
        content_type="application/json",
        user_id=user_id,
        provider=provider,
        batch_id=batch_id,
        payload_ref=payload_ref,
    )

    return UploadDataResponse(status_code=202, response="Import task queued successfully", user_id=user_id)
