"""Celery task for Garmin backfill requests with per-type status tracking.

This task manages the fetching of historical Garmin data using 30-day batch requests.
Each of the 16 data types is tracked independently with status: pending|triggered|success|failed.

Flow:
1. start_full_backfill() - Initialize tracking for all 16 types, trigger first type
2. trigger_backfill_for_type() - Trigger backfill for a specific type
3. mark_type_success() - Called by webhook when data received
4. trigger_next_pending_type() - Chain to next pending type
"""

from datetime import datetime, timedelta, timezone
from logging import getLogger
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException

from app.database import SessionLocal
from app.integrations.redis_client import get_redis_client
from app.repositories.user_connection_repository import UserConnectionRepository
from app.services.providers.factory import ProviderFactory
from app.services.providers.garmin.backfill_config import (
    ACTIVITY_API_TYPES,
    ALL_DATA_TYPES,
    BACKFILL_CHUNK_DAYS,
    BACKFILL_WINDOW_COUNT,
    DELAY_AFTER_RATE_LIMIT,
    DELAY_BETWEEN_TYPES,
    MAX_BACKFILL_DAYS,
    MAX_TYPE_ATTEMPTS,
    REDIS_PREFIX,
    REDIS_TTL,
    TRIGGERED_TIMEOUT_SECONDS,
)
from app.services.providers.garmin.handlers.backfill import GarminBackfillService
from app.utils.sentry_helpers import log_and_capture_error
from app.utils.structured_logging import log_structured
from celery import shared_task

logger = getLogger(__name__)


def _get_key(user_id: str | UUID, *parts: str) -> str:
    """Generate Redis key for backfill tracking."""
    return ":".join([REDIS_PREFIX, str(user_id), *parts])


def set_trace_id(user_id: str | UUID) -> str:
    """Generate and store a trace ID for a user's backfill session."""
    redis_client = get_redis_client()
    trace_id = str(uuid4())[:8]  # Short trace ID for readability
    redis_client.setex(_get_key(user_id, "trace_id"), REDIS_TTL, trace_id)
    return trace_id


def get_trace_id(user_id: str | UUID, data_type: str | None = None) -> str | None:
    """Get the active backfill trace ID for a user, optionally per-type.

    Args:
        user_id: UUID string of the user
        data_type: If provided, returns the per-type trace ID instead of session trace ID
    """
    redis_client = get_redis_client()
    if data_type:
        return redis_client.get(_get_key(user_id, "types", data_type, "trace_id"))
    return redis_client.get(_get_key(user_id, "trace_id"))


def set_type_trace_id(user_id: str | UUID, data_type: str) -> str:
    """Generate and store a per-type trace ID for a specific backfill data type."""
    redis_client = get_redis_client()
    trace_id = str(uuid4())[:8]
    redis_client.setex(_get_key(user_id, "types", data_type, "trace_id"), REDIS_TTL, trace_id)
    return trace_id


def get_backfill_status(user_id: str | UUID) -> dict[str, Any]:
    """Get current backfill status for a user including all 16 types.

    Returns:
        {
            "overall_status": "pending" | "in_progress" | "complete" | "partial",
            "types": {
                "sleeps": {"status": "success", "completed_at": "..."},
                "dailies": {"status": "triggered", "triggered_at": "..."},
                "hrv": {"status": "failed", "error": "..."},
                ...
            },
            "success_count": 5,
            "failed_count": 1,
            "pending_count": 10,
            "in_progress": bool,  # Legacy compatibility
        }
    """
    redis_client = get_redis_client()
    user_id_str = str(user_id)

    types_status: dict[str, dict[str, Any]] = {}
    success_count = 0
    failed_count = 0
    pending_count = 0
    triggered_count = 0
    skipped_count = 0

    for data_type in ALL_DATA_TYPES:
        type_status = redis_client.get(_get_key(user_id_str, "types", data_type, "status"))
        status = type_status if type_status else "pending"

        type_info: dict[str, Any] = {"status": status}

        # Include per-type trace ID and skip count if available
        type_tid = redis_client.get(_get_key(user_id_str, "types", data_type, "trace_id"))
        if type_tid:
            type_info["trace_id"] = type_tid

        skip_cnt = redis_client.get(_get_key(user_id_str, "types", data_type, "skip_count"))
        if skip_cnt:
            type_info["skip_count"] = int(skip_cnt)

        match status:
            case "triggered":
                triggered_at = redis_client.get(_get_key(user_id_str, "types", data_type, "triggered_at"))
                if triggered_at:
                    type_info["triggered_at"] = triggered_at
                triggered_count += 1
            case "success":
                completed_at = redis_client.get(_get_key(user_id_str, "types", data_type, "completed_at"))
                if completed_at:
                    type_info["completed_at"] = completed_at
                success_count += 1
            case "failed":
                error = redis_client.get(_get_key(user_id_str, "types", data_type, "error"))
                if error:
                    type_info["error"] = error
                failed_count += 1
            case "skipped":
                skipped_count += 1
            case _:
                pending_count += 1

        types_status[data_type] = type_info

    # Determine overall status
    # "skipped" types are treated like in_progress (chain isn't done yet)
    if success_count == len(ALL_DATA_TYPES):
        overall_status = "complete"
    elif success_count > 0 and failed_count > 0 and pending_count == 0 and triggered_count == 0 and skipped_count == 0:
        overall_status = "partial"
    elif triggered_count > 0 or skipped_count > 0 or (success_count > 0 and pending_count > 0):
        overall_status = "in_progress"
    else:
        overall_status = "pending"

    completed_windows = get_completed_window_count(user_id_str)

    return {
        "overall_status": overall_status,
        "types": types_status,
        "success_count": success_count,
        "failed_count": failed_count,
        "pending_count": pending_count,
        "triggered_count": triggered_count,
        "skipped_count": skipped_count,
        "total_types": len(ALL_DATA_TYPES),
        # Legacy compatibility
        "in_progress": overall_status == "in_progress",
        # Window tracking
        "current_window": get_current_window(user_id_str),
        "total_windows": get_total_windows(user_id_str),
        "completed_windows": completed_windows,
        "days_completed": completed_windows * BACKFILL_CHUNK_DAYS,
        "target_days": MAX_BACKFILL_DAYS,
    }


def get_pending_types(user_id: str | UUID) -> list[str]:
    """Get list of pending data types for a user."""
    redis_client = get_redis_client()
    user_id_str = str(user_id)
    pending = []

    for data_type in ALL_DATA_TYPES:
        status = redis_client.get(_get_key(user_id_str, "types", data_type, "status"))
        if not status or status == "pending":
            pending.append(data_type)

    return pending


def mark_type_triggered(user_id: str | UUID, data_type: str) -> None:
    """Mark a data type as triggered (backfill request sent)."""
    redis_client = get_redis_client()
    user_id_str = str(user_id)
    now = datetime.now(timezone.utc).isoformat()

    redis_client.setex(_get_key(user_id_str, "types", data_type, "status"), REDIS_TTL, "triggered")
    redis_client.setex(_get_key(user_id_str, "types", data_type, "triggered_at"), REDIS_TTL, now)

    trace_id = get_trace_id(user_id_str)
    type_trace_id = get_trace_id(user_id_str, data_type)
    log_structured(
        logger,
        "info",
        "Marked type as triggered",
        provider="garmin",
        trace_id=trace_id,
        type_trace_id=type_trace_id,
        data_type=data_type,
        user_id=user_id_str,
    )


def mark_type_success(user_id: str | UUID, data_type: str) -> bool:
    """Mark a data type as successfully completed (webhook received data).

    Returns:
        True if this was a new transition (type was not already 'success').
        False if the type was already marked as success (duplicate webhook).
    """
    redis_client = get_redis_client()
    user_id_str = str(user_id)

    # Check if already success to avoid duplicate triggers
    current_status = redis_client.get(_get_key(user_id_str, "types", data_type, "status"))
    if current_status == "success":
        return False

    now = datetime.now(timezone.utc).isoformat()
    redis_client.setex(_get_key(user_id_str, "types", data_type, "status"), REDIS_TTL, "success")
    redis_client.setex(_get_key(user_id_str, "types", data_type, "completed_at"), REDIS_TTL, now)

    trace_id = get_trace_id(user_id_str)
    type_trace_id = get_trace_id(user_id_str, data_type)
    log_structured(
        logger,
        "info",
        "Marked type as success",
        provider="garmin",
        trace_id=trace_id,
        type_trace_id=type_trace_id,
        data_type=data_type,
        user_id=user_id_str,
    )
    return True


def mark_type_failed(user_id: str | UUID, data_type: str, error: str) -> None:
    """Mark a data type as failed."""
    redis_client = get_redis_client()
    user_id_str = str(user_id)

    redis_client.setex(_get_key(user_id_str, "types", data_type, "status"), REDIS_TTL, "failed")
    redis_client.setex(_get_key(user_id_str, "types", data_type, "error"), REDIS_TTL, error)

    trace_id = get_trace_id(user_id_str)
    type_trace_id = get_trace_id(user_id_str, data_type)
    log_structured(
        logger,
        "error",
        "Marked type as failed",
        provider="garmin",
        trace_id=trace_id,
        type_trace_id=type_trace_id,
        data_type=data_type,
        error=error,
        user_id=user_id_str,
    )


def reset_type_status(user_id: str | UUID, data_type: str) -> None:
    """Reset a data type to pending status (for retry)."""
    redis_client = get_redis_client()
    user_id_str = str(user_id)

    # Delete all keys for this type
    for key_suffix in ["status", "triggered_at", "completed_at", "error", "trace_id"]:
        redis_client.delete(_get_key(user_id_str, "types", data_type, key_suffix))

    log_structured(
        logger,
        "info",
        "Reset type status",
        provider="garmin",
        data_type=data_type,
        user_id=user_id_str,
    )


def mark_type_skipped(user_id: str | UUID, data_type: str) -> int:
    """Mark a data type as skipped (timed out waiting for webhook).

    Returns:
        The new skip_count for this type.
    """
    redis_client = get_redis_client()
    user_id_str = str(user_id)

    redis_client.setex(_get_key(user_id_str, "types", data_type, "status"), REDIS_TTL, "skipped")

    # Increment skip count (persists across retries)
    skip_key = _get_key(user_id_str, "types", data_type, "skip_count")
    new_count = redis_client.incr(skip_key)
    redis_client.expire(skip_key, REDIS_TTL)

    trace_id = get_trace_id(user_id_str)
    type_trace_id = get_trace_id(user_id_str, data_type)
    log_structured(
        logger,
        "warn",
        "Marked type as skipped (timeout)",
        provider="garmin",
        trace_id=trace_id,
        type_trace_id=type_trace_id,
        data_type=data_type,
        skip_count=new_count,
        user_id=user_id_str,
    )
    return new_count


def get_skipped_types(user_id: str | UUID) -> list[str]:
    """Get list of skipped data types for a user."""
    redis_client = get_redis_client()
    user_id_str = str(user_id)
    skipped = []

    for data_type in ALL_DATA_TYPES:
        status = redis_client.get(_get_key(user_id_str, "types", data_type, "status"))
        if status == "skipped":
            skipped.append(data_type)

    return skipped


def get_type_skip_count(user_id: str | UUID, data_type: str) -> int:
    """Get the number of times a type has been skipped."""
    redis_client = get_redis_client()
    count = redis_client.get(_get_key(str(user_id), "types", data_type, "skip_count"))
    return int(count) if count else 0


def init_window_state(user_id: str | UUID, total_windows: int = BACKFILL_WINDOW_COUNT) -> None:
    """Initialize multi-window backfill state in Redis."""
    redis_client = get_redis_client()
    uid = str(user_id)
    anchor = datetime.now(timezone.utc).isoformat()
    redis_client.setex(_get_key(uid, "window", "current"), REDIS_TTL, "0")
    redis_client.setex(_get_key(uid, "window", "total"), REDIS_TTL, str(total_windows))
    redis_client.setex(_get_key(uid, "window", "anchor_ts"), REDIS_TTL, anchor)
    redis_client.setex(_get_key(uid, "window", "completed_count"), REDIS_TTL, "0")


def get_current_window(user_id: str | UUID) -> int:
    """Get current window index (0-indexed)."""
    redis_client = get_redis_client()
    val = redis_client.get(_get_key(str(user_id), "window", "current"))
    return int(val) if val else 0


def get_total_windows(user_id: str | UUID) -> int:
    """Get total number of windows for this backfill."""
    redis_client = get_redis_client()
    val = redis_client.get(_get_key(str(user_id), "window", "total"))
    return int(val) if val else BACKFILL_WINDOW_COUNT


def get_anchor_timestamp(user_id: str | UUID) -> datetime:
    """Get the fixed anchor timestamp for window calculation."""
    redis_client = get_redis_client()
    val = redis_client.get(_get_key(str(user_id), "window", "anchor_ts"))
    if val:
        return datetime.fromisoformat(val)
    return datetime.now(timezone.utc)


def get_window_date_range(user_id: str | UUID) -> tuple[datetime, datetime]:
    """Get (start_time, end_time) for the current window.

    Window 0: anchor-30d  →  anchor
    Window 1: anchor-60d  →  anchor-30d
    Window N: anchor-(N+1)*30d  →  anchor-N*30d
    """
    anchor = get_anchor_timestamp(user_id)
    window = get_current_window(user_id)
    chunk = BACKFILL_CHUNK_DAYS
    end_time = anchor - timedelta(days=window * chunk)
    start_time = anchor - timedelta(days=(window + 1) * chunk)
    return start_time, end_time


def get_completed_window_count(user_id: str | UUID) -> int:
    """Get number of completed windows."""
    redis_client = get_redis_client()
    val = redis_client.get(_get_key(str(user_id), "window", "completed_count"))
    return int(val) if val else 0


def advance_window(user_id: str | UUID) -> bool:
    """Advance to next window. Returns True if more windows remain."""
    redis_client = get_redis_client()
    uid = str(user_id)

    # Increment completed count
    completed_key = _get_key(uid, "window", "completed_count")
    redis_client.incr(completed_key)
    redis_client.expire(completed_key, REDIS_TTL)

    # Increment current window
    current_key = _get_key(uid, "window", "current")
    new_window = redis_client.incr(current_key)
    redis_client.expire(current_key, REDIS_TTL)

    total = get_total_windows(uid)
    if new_window >= total:
        return False

    # Reset all 16 types to pending for the new window
    for data_type in ALL_DATA_TYPES:
        reset_type_status(uid, data_type)
        # Delete skip_count keys (fresh retry budget per window)
        redis_client.delete(_get_key(uid, "types", data_type, "skip_count"))

    trace_id = get_trace_id(uid)
    log_structured(
        logger,
        "info",
        "Advanced to next backfill window",
        provider="garmin",
        trace_id=trace_id,
        user_id=uid,
        window=new_window,
        total_windows=total,
    )
    return True


def complete_backfill(user_id: str | UUID) -> None:
    """Mark entire backfill as complete (all types processed)."""
    redis_client = get_redis_client()
    user_id_str = str(user_id)

    # Set overall complete marker with shorter TTL (1 day)
    redis_client.setex(_get_key(user_id_str, "overall_complete"), 24 * 60 * 60, "1")

    trace_id = get_trace_id(user_id_str)
    completed_windows = get_completed_window_count(user_id_str)
    log_structured(
        logger,
        "info",
        "Completed full backfill",
        provider="garmin",
        trace_id=trace_id,
        user_id=user_id_str,
        completed_windows=completed_windows,
    )


@shared_task
def start_full_backfill(user_id: str) -> dict[str, Any]:
    """Initialize and start full 365-day backfill (12 x 30-day windows) for all 16 data types.

    This is called after OAuth connection to auto-trigger historical sync.
    Triggers the first type and the rest will chain via webhooks.

    Args:
        user_id: UUID string of the user

    Returns:
        Dict with initialization status
    """
    try:
        UUID(user_id)  # Validate UUID format
    except ValueError as e:
        log_structured(
            logger,
            "error",
            "Invalid user_id",
            user_id=user_id,
            error=str(e),
        )
        return {"error": f"Invalid user_id: {e}"}

    # Generate trace ID for this backfill session
    trace_id = set_trace_id(user_id)

    # Initialize multi-window state
    init_window_state(user_id, total_windows=BACKFILL_WINDOW_COUNT)

    log_structured(
        logger,
        "info",
        "Starting full backfill",
        provider="garmin",
        trace_id=trace_id,
        user_id=user_id,
        total_types=len(ALL_DATA_TYPES),
        total_windows=BACKFILL_WINDOW_COUNT,
        target_days=MAX_BACKFILL_DAYS,
    )

    # Reset all type statuses to pending
    for data_type in ALL_DATA_TYPES:
        reset_type_status(user_id, data_type)

    # Trigger the first type (with small delay to avoid immediate burst)
    first_type = ALL_DATA_TYPES[0]
    trigger_backfill_for_type.apply_async(args=[user_id, first_type], countdown=1)

    return {
        "status": "started",
        "user_id": user_id,
        "trace_id": trace_id,
        "total_types": len(ALL_DATA_TYPES),
        "total_windows": BACKFILL_WINDOW_COUNT,
        "target_days": MAX_BACKFILL_DAYS,
        "first_type": first_type,
    }


@shared_task
def check_triggered_timeout(user_id: str, data_type: str) -> dict[str, Any]:
    """Check if a triggered type has timed out and skip/fail it.

    Scheduled by trigger_backfill_for_type with countdown=TRIGGERED_TIMEOUT_SECONDS.
    If the type is still "triggered" after the timeout, it means Garmin never sent
    a webhook (e.g., user has no data for this type).

    Args:
        user_id: UUID string of the user
        data_type: The data type to check

    Returns:
        Dict with timeout check result
    """
    redis_client = get_redis_client()
    user_id_str = str(user_id)

    trace_id = get_trace_id(user_id_str)
    type_trace_id = get_trace_id(user_id_str, data_type)

    # 1. Read current status
    status = redis_client.get(_get_key(user_id_str, "types", data_type, "status"))

    # 2. If not "triggered" → already resolved by webhook
    if status != "triggered":
        log_structured(
            logger,
            "info",
            "Timeout check: type already resolved",
            provider="garmin",
            trace_id=trace_id,
            type_trace_id=type_trace_id,
            data_type=data_type,
            current_status=status,
            user_id=user_id_str,
        )
        return {"status": "already_resolved", "current_status": status}

    # 3. Verify triggered_at is actually older than TRIGGERED_TIMEOUT_SECONDS
    triggered_at_str = redis_client.get(_get_key(user_id_str, "types", data_type, "triggered_at"))
    if triggered_at_str:
        triggered_at = datetime.fromisoformat(triggered_at_str)
        elapsed = (datetime.now(timezone.utc) - triggered_at).total_seconds()
        if elapsed < TRIGGERED_TIMEOUT_SECONDS:
            # Re-triggered since timeout was scheduled; reschedule with remaining time
            remaining = int(TRIGGERED_TIMEOUT_SECONDS - elapsed) + 1
            log_structured(
                logger,
                "info",
                "Timeout check: not yet expired, rescheduling",
                provider="garmin",
                trace_id=trace_id,
                type_trace_id=type_trace_id,
                data_type=data_type,
                elapsed=int(elapsed),
                remaining=remaining,
                user_id=user_id_str,
            )
            check_triggered_timeout.apply_async(args=[user_id, data_type], countdown=remaining)
            return {"status": "rescheduled", "remaining": remaining}

    # 4. Read skip count for this type
    skip_count = get_type_skip_count(user_id_str, data_type)

    # 5. If skip_count + 1 >= MAX_TYPE_ATTEMPTS → mark failed
    if skip_count + 1 >= MAX_TYPE_ATTEMPTS:
        mark_type_failed(
            user_id_str,
            data_type,
            f"Timeout after {MAX_TYPE_ATTEMPTS} attempts (no webhook received)",
        )
        log_structured(
            logger,
            "warn",
            "Type failed after max timeout attempts",
            provider="garmin",
            trace_id=trace_id,
            type_trace_id=type_trace_id,
            data_type=data_type,
            attempts=skip_count + 1,
            user_id=user_id_str,
        )
    else:
        # 6. Mark as skipped
        mark_type_skipped(user_id_str, data_type)

    # 7. Chain to next type
    trigger_next_pending_type.apply_async(args=[user_id], countdown=DELAY_BETWEEN_TYPES)

    return {
        "status": "timed_out",
        "data_type": data_type,
        "skip_count": skip_count + 1,
        "action": "failed" if skip_count + 1 >= MAX_TYPE_ATTEMPTS else "skipped",
    }


@shared_task
def trigger_backfill_for_type(user_id: str, data_type: str) -> dict[str, Any]:
    """Trigger backfill for a specific data type.

    Args:
        user_id: UUID string of the user
        data_type: One of the 16 data types

    Returns:
        Dict with trigger status
    """
    if data_type not in ALL_DATA_TYPES:
        return {"error": f"Invalid data type: {data_type}"}

    try:
        user_uuid = UUID(user_id)
    except ValueError as e:
        log_structured(
            logger,
            "error",
            "Invalid user_id",
            user_id=user_id,
            error=str(e),
        )
        return {"error": f"Invalid user_id: {e}"}

    trace_id = get_trace_id(user_id)
    type_trace_id = set_type_trace_id(user_id, data_type)

    # Calculate date range from the current window
    start_time, end_time = get_window_date_range(user_id)
    current_window = get_current_window(user_id)

    log_structured(
        logger,
        "info",
        "Triggering backfill for type",
        provider="garmin",
        trace_id=trace_id,
        type_trace_id=type_trace_id,
        data_type=data_type,
        window=current_window,
        start_date=str(start_time.date()),
        end_date=str(end_time.date()),
        user_id=user_id,
    )

    with SessionLocal() as db:
        try:
            # Get Garmin connection
            connection_repo = UserConnectionRepository()
            connection = connection_repo.get_by_user_and_provider(db, user_uuid, "garmin")

            if not connection:
                error = "No Garmin connection"
                mark_type_failed(user_id, data_type, error)
                return {"error": error}

            # Get backfill service from factory
            factory = ProviderFactory()
            garmin_strategy = factory.get_provider("garmin")

            if not garmin_strategy.oauth:
                error = "Garmin OAuth not configured"
                mark_type_failed(user_id, data_type, error)
                return {"error": error}

            backfill_service = GarminBackfillService(
                provider_name="garmin",
                api_base_url="https://apis.garmin.com",
                oauth=garmin_strategy.oauth,
            )

            # Mark as triggered before making the request
            mark_type_triggered(user_id, data_type)

            # Trigger backfill for single data type
            try:
                result = backfill_service.trigger_backfill(
                    db=db,
                    user_id=user_uuid,
                    data_types=[data_type],
                    start_time=start_time,
                    end_time=end_time,
                    trace_id=trace_id,
                )
            except HTTPException as e:
                # Garmin rejects requests for users connected less than max days ago
                if e.status_code == 400 and "min start time" in str(e.detail):
                    # Retry with shorter range (14 days for Activity API, 31 for Health API)
                    fallback_days = 14 if data_type in ACTIVITY_API_TYPES else 31
                    start_time_fallback = end_time - timedelta(days=fallback_days)
                    log_structured(
                        logger,
                        "info",
                        "Retrying with shorter range",
                        provider="garmin",
                        trace_id=trace_id,
                        type_trace_id=type_trace_id,
                        data_type=data_type,
                        fallback_days=fallback_days,
                        user_id=user_id,
                    )
                    result = backfill_service.trigger_backfill(
                        db=db,
                        user_id=user_uuid,
                        data_types=[data_type],
                        start_time=start_time_fallback,
                        end_time=end_time,
                        trace_id=trace_id,
                    )
                else:
                    raise

            # Check result
            if data_type in result.get("failed", {}):
                error = result["failed"][data_type]
                mark_type_failed(user_id, data_type, error)

                # 400 "Endpoint not enabled" = app-level config issue in Garmin portal.
                # All types will fail identically, so stop the chain immediately.
                if "endpoint not enabled" in error.lower():
                    error_msg = "Backfill endpoints not enabled for this app in Garmin developer portal."
                    log_structured(
                        logger,
                        "warn",
                        "Endpoint not enabled: stopping backfill for all types",
                        provider="garmin",
                        trace_id=trace_id,
                        type_trace_id=type_trace_id,
                        data_type=data_type,
                        user_id=user_id,
                    )
                    pending = get_pending_types(user_id)
                    for pending_type in pending:
                        mark_type_failed(user_id, pending_type, error_msg)
                    return {"status": "failed", "error": error_msg}

                # Determine delay based on error type
                is_rate_limit = "429" in error or "rate limit" in error.lower()
                delay = DELAY_AFTER_RATE_LIMIT if is_rate_limit else DELAY_BETWEEN_TYPES
                if is_rate_limit:
                    log_structured(
                        logger,
                        "warn",
                        "Rate limit hit, delaying next type",
                        provider="garmin",
                        trace_id=trace_id,
                        type_trace_id=type_trace_id,
                        data_type=data_type,
                        delay_seconds=delay,
                        user_id=user_id,
                    )
                # Still trigger next type even if this one failed (with delay)
                trigger_next_pending_type.apply_async(args=[user_id], countdown=delay)
                return {"status": "failed", "error": error}

            # Schedule timeout check in case Garmin never sends a webhook
            check_triggered_timeout.apply_async(args=[user_id, data_type], countdown=TRIGGERED_TIMEOUT_SECONDS)

            return {
                "status": "triggered",
                "data_type": data_type,
                "start_date": start_time.isoformat(),
                "end_date": end_time.isoformat(),
            }

        except HTTPException as e:
            error = str(e.detail)
            log_structured(
                logger,
                "error",
                "HTTP error triggering backfill",
                provider="garmin",
                trace_id=trace_id,
                type_trace_id=type_trace_id,
                data_type=data_type,
                status_code=e.status_code,
                error=error,
                user_id=user_id,
            )
            mark_type_failed(user_id, data_type, error)

            # 403 = user didn't grant HISTORICAL_DATA_EXPORT permission during OAuth
            # 400 "Endpoint not enabled" = app-level config issue in Garmin portal
            # Both cases affect all types identically, so don't chain to next type
            is_endpoint_not_enabled = e.status_code == 400 and "endpoint not enabled" in error.lower()
            if e.status_code == 403 or is_endpoint_not_enabled:
                if is_endpoint_not_enabled:
                    error_msg = "Backfill endpoints not enabled for this app in Garmin developer portal."
                    log_msg = "Endpoint not enabled: stopping backfill for all types"
                else:
                    error_msg = "Historical data access not granted. User must re-authorize."
                    log_msg = "403: marking all remaining types as failed"
                log_structured(
                    logger,
                    "warn",
                    log_msg,
                    provider="garmin",
                    trace_id=trace_id,
                    type_trace_id=type_trace_id,
                    data_type=data_type,
                    user_id=user_id,
                )
                # Mark all remaining pending types as failed
                pending = get_pending_types(user_id)
                for pending_type in pending:
                    mark_type_failed(user_id, pending_type, error_msg)
                return {"status": "failed", "error": error_msg}

            # Determine delay based on error type
            is_rate_limit = e.status_code == 429 or "rate limit" in error.lower()
            delay = DELAY_AFTER_RATE_LIMIT if is_rate_limit else DELAY_BETWEEN_TYPES
            if is_rate_limit:
                log_structured(
                    logger,
                    "warn",
                    "Rate limit hit, delaying next type",
                    provider="garmin",
                    trace_id=trace_id,
                    type_trace_id=type_trace_id,
                    data_type=data_type,
                    delay_seconds=delay,
                    user_id=user_id,
                )
            # Try to continue with next type (with delay)
            trigger_next_pending_type.apply_async(args=[user_id], countdown=delay)
            return {"status": "failed", "error": error}

        except Exception as e:
            error = str(e)
            log_and_capture_error(
                e,
                logger,
                f"Error triggering backfill for type {data_type}: {e}",
                extra={
                    "user_id": user_id,
                    "trace_id": trace_id,
                    "type_trace_id": type_trace_id,
                    "data_type": data_type,
                },
            )
            mark_type_failed(user_id, data_type, error)
            # Try to continue with next type (with small delay)
            trigger_next_pending_type.apply_async(args=[user_id], countdown=DELAY_BETWEEN_TYPES)
            return {"error": error}


@shared_task
def trigger_next_pending_type(user_id: str) -> dict[str, Any]:
    """Trigger the next pending data type in the backfill sequence.

    Called after a webhook receives data for a type, or after a type fails.

    Args:
        user_id: UUID string of the user

    Returns:
        Dict with status
    """
    trace_id = get_trace_id(user_id)
    pending_types = get_pending_types(user_id)

    if not pending_types:
        # Check for skipped types that need retry
        skipped_types = get_skipped_types(user_id)
        if skipped_types:
            log_structured(
                logger,
                "info",
                "Retrying skipped types",
                provider="garmin",
                trace_id=trace_id,
                user_id=user_id,
                skipped_types=skipped_types,
            )
            # Reset skipped types to pending for retry
            for data_type in skipped_types:
                reset_type_status(user_id, data_type)
            # Trigger the first one
            trigger_backfill_for_type.apply_async(args=[user_id, skipped_types[0]], countdown=DELAY_BETWEEN_TYPES)
            return {"status": "retrying_skipped", "types": skipped_types}

        # No pending, no skipped — current window done. Try advancing.
        has_more = advance_window(user_id)
        if has_more:
            current_window = get_current_window(user_id)
            log_structured(
                logger,
                "info",
                "Window complete, advancing to next",
                provider="garmin",
                trace_id=trace_id,
                user_id=user_id,
                window=current_window,
                total_windows=get_total_windows(user_id),
            )
            first_type = ALL_DATA_TYPES[0]
            trigger_backfill_for_type.apply_async(args=[user_id, first_type], countdown=DELAY_BETWEEN_TYPES)
            return {"status": "advancing_window", "window": current_window}

        # All windows exhausted — finalize
        status = get_backfill_status(user_id)
        if status["failed_count"] == 0:
            complete_backfill(user_id)
            log_structured(
                logger,
                "info",
                "Backfill complete",
                provider="garmin",
                trace_id=trace_id,
                user_id=user_id,
                success_count=status["success_count"],
                completed_windows=status["completed_windows"],
            )
            return {"status": "complete", "success_count": status["success_count"]}
        log_structured(
            logger,
            "info",
            "Backfill finished with failures",
            provider="garmin",
            trace_id=trace_id,
            user_id=user_id,
            success_count=status["success_count"],
            failed_count=status["failed_count"],
            completed_windows=status["completed_windows"],
        )
        return {
            "status": "partial",
            "success_count": status["success_count"],
            "failed_count": status["failed_count"],
        }

    next_type = pending_types[0]
    log_structured(
        logger,
        "info",
        "Triggering next backfill type",
        provider="garmin",
        trace_id=trace_id,
        user_id=user_id,
        next_type=next_type,
        remaining=len(pending_types),
    )

    # Add small delay between types to avoid rate limiting
    trigger_backfill_for_type.apply_async(args=[user_id, next_type], countdown=DELAY_BETWEEN_TYPES)

    return {"status": "continuing", "next_type": next_type, "pending_count": len(pending_types)}


# Alias for backwards compatibility
trigger_next_backfill = trigger_next_pending_type
continue_garmin_backfill = trigger_next_pending_type
