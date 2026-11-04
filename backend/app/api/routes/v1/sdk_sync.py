import json
import uuid
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.config import settings
from app.constants.sdk_providers import SDK_PROVIDERS, normalize_sdk_provider
from app.database import DbSession
from app.integrations.celery.tasks.process_sdk_upload_task import process_sdk_upload
from app.schemas.providers.mobile_sdk import SDKSyncState, SyncRequest
from app.schemas.responses.upload import UploadDataResponse
from app.services import user_service
from app.services.raw_payload_storage import put_payload_to_s3, store_raw_payload
from app.services.sync_status_service import get_sdk_sync_state
from app.utils.api_utils import inline_schema_defs
from app.utils.auth import SDKAuthDep
from app.utils.exceptions import unknown_provider
from app.utils.sdk_request_metadata import sdk_request_metadata
from app.utils.structured_logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


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
    request: Request,
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
    raw_provider = str(body.get("provider") or "").lower()

    # Validate provider (routing decision — needed to select an import service)
    provider = normalize_sdk_provider(raw_provider)
    if provider is None:
        raise unknown_provider(raw_provider, ("body", "provider"), SDK_PROVIDERS)
    # The worker and import service re-read the provider from the payload, so the
    # canonical slug has to replace the alias here rather than travel alongside it.
    body["provider"] = provider

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
    logger.info(
        "SDK sync batch received",
        action=f"{provider}_sdk_batch_received",
        batch_id=batch_id,
        user_id=user_id,
        provider=provider,
        records_count=records_count,
        workouts_count=workouts_count,
        sleep_count=sleep_count,
        total_items=records_count + workouts_count + sleep_count,
        **sdk_request_metadata(request.headers, body.get("sdkVersion")),
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
        exc = HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to persist payload; please retry.",
        )
        logger.error(
            "Failed to persist SDK payload to S3; rejecting batch",
            exc_info=exc,
            action="sdk_payload_persist_failed",
            batch_id=batch_id,
            user_id=user_id,
            provider=provider,
        )
        raise exc

    process_sdk_upload.delay(
        content=None if offload else content_str,
        content_type="application/json",
        user_id=user_id,
        provider=provider,
        batch_id=batch_id,
        payload_ref=payload_ref,
        # SDK versions that do not send these yet have no session, so the batch is live.
        sync_session_id=body.get("syncSessionId"),
        sync_type=body.get("syncType"),
    )

    return UploadDataResponse(status_code=202, response="Import task queued successfully", user_id=user_id)


@router.get("/sdk/users/{user_id}/sync/status")
def get_sdk_sync_status(
    user_id: UUID,
    provider: Annotated[str, Query(description="SDK provider slug, e.g. `apple`, `samsung`, `health_connect`.")],
    db: DbSession,
    auth: SDKAuthDep,
) -> SDKSyncState:
    """Where the user's SDK sync for one provider stands, as the server sees it.

    The server is the source of truth for sync progress; the device's own state is only a
    cache. Call this after login, before starting a sync, to restore that state:

    - `historicalSyncCompleted: true` - the historical export finished; only live sync is
      left, continuing from `syncedUntil`.
    - `historicalSyncCompleted: false` - the export has not finished. It runs newest first, so
      each type in `dataTypes` with `historicalSyncCompleted: false` resumes backwards from its
      `exportedRange.startDate`. Types not listed have no data on the server yet.
    - `historicalSyncCompleted: null` - no historical export on record: nothing synced yet, or
      an SDK version that does not send `syncSessionId`, so the server cannot tell. The same
      applies per type in `dataTypes`.
    - `syncedUntil: null` and empty `dataTypes` - nothing synced yet; start a full export.

    A user who has never synced gets that empty state with 200, not 404.
    """
    if auth.auth_type == "sdk_token" and (not auth.user_id or str(auth.user_id) != str(user_id)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token does not match user_id",
        )

    canonical = normalize_sdk_provider(provider)
    if canonical is None:
        raise unknown_provider(provider, ("query", "provider"), SDK_PROVIDERS)

    user_service.get(db, user_id, raise_404=True)
    return get_sdk_sync_state(db, user_id, canonical)
