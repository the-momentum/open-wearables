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


@router.post("/sdk/users/{user_id}/logs", status_code=status.HTTP_202_ACCEPTED)
def submit_sdk_logs(
    user_id: str,
    body: SDKLogRequest,
    auth: SDKAuthDep,
) -> UploadDataResponse:
    """Accept SDK diagnostic log events and store to raw S3 storage.

    Used for observability into mobile SDK sync behavior (background task
    lifecycle, device state, sync success/failure).
    """
    if auth.auth_type == "sdk_token" and (not auth.user_id or str(auth.user_id) != user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token does not match user_id",
        )

    batch_id = str(uuid.uuid4())
    provider = (body.provider or "unknown").lower()
    event_types = [e.eventType for e in body.events]

    log_structured(
        logger,
        "info",
        "SDK log events received",
        action="sdk_logs_received",
        batch_id=batch_id,
        user_id=user_id,
        provider=provider,
        event_count=len(body.events),
        event_types=event_types,
        sdk_version=body.sdkVersion,
    )

    store_raw_payload(
        source="sdk_logs",
        provider=provider,
        payload=body.model_dump_json(),
        user_id=user_id,
        trace_id=batch_id,
    )

    return UploadDataResponse(
        status_code=202,
        response="Log events stored successfully",
        user_id=user_id,
    )
