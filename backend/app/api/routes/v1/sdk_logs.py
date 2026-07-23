import json
import uuid
from logging import getLogger

from fastapi import APIRouter, HTTPException, status

from app.schemas.providers.mobile_sdk import SDKLogRequest
from app.schemas.responses.upload import UploadDataResponse
from app.services.raw_payload_storage import store_raw_payload
from app.utils.auth import SDKAuthDep
from app.utils.structured_logging import log_structured

router = APIRouter()
logger = getLogger(__name__)


@router.post(
    "/sdk/users/{user_id}/logs",
    status_code=status.HTTP_202_ACCEPTED,
    # body is `dict` at runtime; keep the SDKLogRequest shape in the OpenAPI docs.
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": SDKLogRequest.model_json_schema()}},
        }
    },
)
def submit_sdk_logs(
    user_id: str,
    body: dict,
    auth: SDKAuthDep,
) -> UploadDataResponse:
    """Accept SDK diagnostic log events and store to raw S3 storage.

    Used for observability into mobile SDK sync behavior (background task
    lifecycle, device state, sync success/failure).

    Raw dict, not SDKLogRequest: this is an observability sink, so a batch is stored
    unconditionally — schema-validating here would 400 and discard diagnostics on one
    unknown event type, exactly when they matter most.
    """
    if auth.auth_type == "sdk_token" and (not auth.user_id or str(auth.user_id) != user_id):
        log_structured(
            logger,
            "warning",
            "SDK logs rejected: token does not match user_id",
            action="sdk_logs_rejected",
            user_id=user_id,
            status_code=403,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token does not match user_id",
        )

    batch_id = str(uuid.uuid4())
    provider = str(body.get("provider") or "unknown").lower()

    # Best-effort field extraction (structure not validated).
    raw_events = body.get("events")
    events = raw_events if isinstance(raw_events, list) else []
    event_types = [e.get("eventType") for e in events if isinstance(e, dict)]

    log_structured(
        logger,
        "info",
        "SDK log events received",
        action="sdk_logs_received",
        batch_id=batch_id,
        user_id=user_id,
        provider=provider,
        event_count=len(events),
        event_types=event_types,
        sdk_version=body.get("sdkVersion"),
    )

    store_raw_payload(
        source="sdk_logs",
        provider=provider,
        payload=json.dumps(body),
        user_id=user_id,
        trace_id=batch_id,
    )

    return UploadDataResponse(
        status_code=202,
        response="Log events stored successfully",
        user_id=user_id,
    )
