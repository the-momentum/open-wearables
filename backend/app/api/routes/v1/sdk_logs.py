import uuid
from logging import getLogger
from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.constants.series_types.sdk import get_series_type_from_metric_type
from app.schemas.providers.mobile_sdk import (
    DeviceStateEvent,
    HistoricalDataSyncStartEvent,
    HistoricalDataTypeSyncEndEvent,
    SDKLogRequest,
)
from app.schemas.responses.upload import UploadDataResponse
from app.services.raw_payload_storage import store_raw_payload
from app.utils.auth import SDKAuthDep
from app.utils.structured_logging import log_structured

router = APIRouter()
logger = getLogger(__name__)

# Only for single-outcome batches: the SDK posts one event plus a device_state snapshot,
# so this flattens onto the line already emitted rather than adding any.
_MAX_FLATTENED_EVENTS = 2


def _event_fields(body: SDKLogRequest) -> dict[str, Any]:
    """Per-event fields worth having queryable in the deployment logs.

    Without these the log records only that an event arrived, so per-type outcomes and
    the foreground/background split are readable only by fetching the S3 payload.
    durationMs is left out: the SDK measures it from the start of the whole run, so every
    type in a run reports the same value.
    """
    fields: dict[str, Any] = {}
    # Several outcomes in one batch cannot share these fields without overwriting
    # each other, so they stay in the stored payload only.
    outcome_count = sum(isinstance(event, HistoricalDataTypeSyncEndEvent) for event in body.events)
    flatten_outcome = len(body.events) <= _MAX_FLATTENED_EVENTS and outcome_count == 1

    for event in body.events:
        match event:
            case DeviceStateEvent():
                fields |= {
                    "task_type": event.taskType,
                    "low_power": event.isLowPowerMode,
                    "thermal_state": event.thermalState,
                }
            case HistoricalDataSyncStartEvent():
                populated = [count for count in event.dataTypeCounts if count.count > 0]
                fields |= {
                    "types_declared": len(populated),
                    "samples_expected": sum(count.count for count in populated),
                }
            case HistoricalDataTypeSyncEndEvent() if flatten_outcome:
                # Sleep and workout identifiers have no series type, so they keep the native one.
                series_type = get_series_type_from_metric_type(event.dataType)
                fields |= {
                    "data_type": series_type.value if series_type else event.dataType,
                    "native_data_type": event.dataType,
                    "success": event.success,
                    "record_count": event.recordCount,
                }

    return {key: value for key, value in fields.items() if value is not None}


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
        **_event_fields(body),
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
