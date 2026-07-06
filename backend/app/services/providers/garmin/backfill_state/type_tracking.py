"""Per-type backfill status tracking in Redis."""

import logging
from datetime import datetime, timezone
from uuid import UUID

from app.integrations.redis_client import get_redis_client
from app.services.providers.garmin.backfill_config import (
    BACKFILL_DATA_TYPES,
    REDIS_TTL,
)
from app.services.providers.garmin.backfill_state.core import _get_key, get_trace_id
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)


def get_pending_types(user_id: str | UUID) -> list[str]:
    """Return data types whose status is pending (not yet triggered)."""
    user_id_str = str(user_id)
    keys = [_get_key(user_id_str, "types", dt, "status") for dt in BACKFILL_DATA_TYPES]
    statuses = get_redis_client().mget(keys)
    return [dt for dt, status in zip(BACKFILL_DATA_TYPES, statuses) if not status or status == "pending"]


def mark_type_triggered(user_id: str | UUID, data_type: str) -> None:
    """Mark a data type as triggered (backfill request sent to Garmin)."""
    user_id_str = str(user_id)
    now = datetime.now(timezone.utc).isoformat()
    get_redis_client().setex(_get_key(user_id_str, "types", data_type, "status"), REDIS_TTL, "triggered")
    get_redis_client().setex(_get_key(user_id_str, "types", data_type, "triggered_at"), REDIS_TTL, now)

    log_structured(
        logger,
        "info",
        "Marked type as triggered",
        provider="garmin",
        trace_id=get_trace_id(user_id_str),
        type_trace_id=get_trace_id(user_id_str, data_type),
        data_type=data_type,
        user_id=user_id_str,
    )


def mark_type_success(user_id: str | UUID, data_type: str) -> bool:
    """Mark a data type as successfully completed (webhook received data).

    Returns:
        True if this was a new transition (type was not already 'success').
        False if the type was already marked as success (duplicate webhook).
    """
    user_id_str = str(user_id)
    current_status = get_redis_client().get(_get_key(user_id_str, "types", data_type, "status"))
    if current_status == "success":
        return False

    now = datetime.now(timezone.utc).isoformat()
    get_redis_client().setex(_get_key(user_id_str, "types", data_type, "status"), REDIS_TTL, "success")
    get_redis_client().setex(_get_key(user_id_str, "types", data_type, "completed_at"), REDIS_TTL, now)

    log_structured(
        logger,
        "info",
        "Marked type as success",
        provider="garmin",
        trace_id=get_trace_id(user_id_str),
        type_trace_id=get_trace_id(user_id_str, data_type),
        data_type=data_type,
        user_id=user_id_str,
    )
    return True


def mark_type_failed(user_id: str | UUID, data_type: str, error: str) -> None:
    """Mark a data type as failed."""
    user_id_str = str(user_id)
    get_redis_client().setex(_get_key(user_id_str, "types", data_type, "status"), REDIS_TTL, "failed")
    get_redis_client().setex(_get_key(user_id_str, "types", data_type, "error"), REDIS_TTL, error)

    log_structured(
        logger,
        "error",
        "Marked type as failed",
        provider="garmin",
        trace_id=get_trace_id(user_id_str),
        type_trace_id=get_trace_id(user_id_str, data_type),
        data_type=data_type,
        error=error,
        user_id=user_id_str,
    )


def reset_type_status(user_id: str | UUID, data_type: str) -> None:
    """Reset a data type to pending status (for retry)."""
    user_id_str = str(user_id)
    for key_suffix in ["status", "triggered_at", "completed_at", "error", "trace_id"]:
        get_redis_client().delete(_get_key(user_id_str, "types", data_type, key_suffix))

    log_structured(
        logger,
        "info",
        "Reset type status",
        provider="garmin",
        data_type=data_type,
        user_id=user_id_str,
    )


def mark_type_timed_out(user_id: str | UUID, data_type: str) -> int:
    """Mark a data type as timed_out (no webhook within the timeout window).

    Returns:
        The new skip_count for this type (kept for diagnostics).
    """
    user_id_str = str(user_id)
    get_redis_client().setex(_get_key(user_id_str, "types", data_type, "status"), REDIS_TTL, "timed_out")

    skip_key = _get_key(user_id_str, "types", data_type, "skip_count")
    new_count = get_redis_client().incr(skip_key)
    get_redis_client().expire(skip_key, REDIS_TTL)

    log_structured(
        logger,
        "warning",
        "Marked type as timed_out (timeout)",
        provider="garmin",
        trace_id=get_trace_id(user_id_str),
        type_trace_id=get_trace_id(user_id_str, data_type),
        data_type=data_type,
        skip_count=new_count,
        user_id=user_id_str,
    )
    return new_count


def get_timed_out_types(user_id: str | UUID) -> list[str]:
    """Return data types whose status is timed_out."""
    user_id_str = str(user_id)
    return [
        dt
        for dt in BACKFILL_DATA_TYPES
        if get_redis_client().get(_get_key(user_id_str, "types", dt, "status")) == "timed_out"
    ]


def get_type_skip_count(user_id: str | UUID, data_type: str) -> int:
    """Return the number of times a type has been skipped/timed-out."""
    count = get_redis_client().get(_get_key(str(user_id), "types", data_type, "skip_count"))
    return int(count) if count else 0
