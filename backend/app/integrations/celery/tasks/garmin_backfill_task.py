"""Celery task for Garmin backfill requests with per-type status tracking.

This task manages the fetching of historical Garmin data using 30-day batch requests.
Each of the data types is tracked independently with status: pending|triggered|success|failed.

Flow:
1. start_full_backfill() - Initialize tracking for all backfill types, trigger first type
2. trigger_backfill_for_type() - Trigger backfill for a specific type
3. mark_type_success() - Called by webhook when data received
4. trigger_next_pending_type() - Chain to next pending type
"""

import json
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
    BACKFILL_CHUNK_DAYS,
    BACKFILL_DATA_TYPES,
    BACKFILL_LOCK_TTL,
    BACKFILL_WINDOW_COUNT,
    DELAY_AFTER_RATE_LIMIT,
    DELAY_BETWEEN_TYPES,
    GC_MAX_ATTEMPTS,
    MAX_BACKFILL_DAYS,
    REDIS_PREFIX,
    REDIS_TTL,
    TRIGGERED_TIMEOUT_SECONDS,
)
from app.services.providers.garmin.handlers.backfill import GarminBackfillService
from app.utils.sentry_helpers import log_and_capture_error
from app.utils.structured_logging import log_structured
from celery import shared_task

logger = getLogger(__name__)
redis_client = get_redis_client()


def _get_key(user_id: str | UUID, *parts: str) -> str:
    """Generate Redis key for backfill tracking."""
    return ":".join([REDIS_PREFIX, str(user_id), *parts])


def set_trace_id(user_id: str | UUID) -> str:
    """Generate and store a trace ID for a user's backfill session."""
    trace_id = str(uuid4())[:8]  # Short trace ID for readability
    redis_client.setex(_get_key(user_id, "trace_id"), REDIS_TTL, trace_id)
    return trace_id


def get_trace_id(user_id: str | UUID, data_type: str | None = None) -> str | None:
    """Get the active backfill trace ID for a user, optionally per-type.

    Args:
        user_id: UUID string of the user
        data_type: If provided, returns the per-type trace ID instead of session trace ID
    """
    if data_type:
        return redis_client.get(_get_key(user_id, "types", data_type, "trace_id"))
    return redis_client.get(_get_key(user_id, "trace_id"))


def set_type_trace_id(user_id: str | UUID, data_type: str) -> str:
    """Generate and store a per-type trace ID for a specific backfill data type."""
    trace_id = str(uuid4())[:8]
    redis_client.setex(_get_key(user_id, "types", data_type, "trace_id"), REDIS_TTL, trace_id)
    return trace_id


def get_backfill_status(user_id: str | UUID) -> dict[str, Any]:
    """Get backfill status with per-window-per-type matrix.

    Completed windows (0..current_window-1) are read from persisted matrix keys.
    The current window is read from flat type keys (live orchestration state).

    Returns:
        {
            "overall_status": "pending" | "in_progress" | "complete" | "cancelled"
                              | "retry_in_progress" | "permanently_failed",
            "current_window": int,
            "total_windows": int,
            "windows": {"0": {"sleeps": "done", ...}, ...},
            "summary": {"sleeps": {"done": 3, "timed_out": 0, "failed": 0}, ...},
            "in_progress": bool,
            "retry_phase": bool,
            "retry_type": str | None,
            "retry_window": int | None,
            "attempt_count": int,
            "max_attempts": int,
            "permanently_failed": bool,
        }
    """
    uid = str(user_id)
    current_window = get_current_window(uid)
    total_windows = get_total_windows(uid)

    windows: dict[str, dict[str, str]] = {}
    summary: dict[str, dict[str, int]] = {dt: {"done": 0, "timed_out": 0, "failed": 0} for dt in BACKFILL_DATA_TYPES}

    # Read completed windows from matrix keys (windows 0..current_window-1)
    for w in range(current_window):
        window_states: dict[str, str] = {}
        for dt in BACKFILL_DATA_TYPES:
            key = f"{REDIS_PREFIX}:{uid}:w:{w}:{dt}:status"
            state = redis_client.get(key) or "pending"
            window_states[dt] = state
            if state in summary[dt]:
                summary[dt][state] += 1
        windows[str(w)] = window_states

    # Read current window from flat type keys (live orchestration state)
    current_states: dict[str, str] = {}
    for dt in BACKFILL_DATA_TYPES:
        flat_status = redis_client.get(_get_key(uid, "types", dt, "status"))

        match flat_status:
            case "success":
                state = "done"
            case "timed_out" | "failed":
                state = str(flat_status)
            case "pending" | "triggered" | None:
                state = "pending"
            case _:  # default case
                state = str(flat_status)

        current_states[dt] = state

        if state in summary[dt]:
            summary[dt][state] += 1

    windows[str(current_window)] = current_states

    # Read retry/GC state
    status_vals = redis_client.mget(
        [
            _get_key(uid, k)
            for k in [
                "lock",
                "cancel_flag",
                "retry_phase",
                "retry_current_type",
                "retry_current_window",
                "attempt_count",
                "permanently_failed",
            ]
        ]
    )

    lock_exists = status_vals[0] is not None
    cancel_flag = status_vals[1] == "1"
    retry_phase_active = status_vals[2] == "1"
    retry_type = status_vals[3]
    retry_window = int(status_vals[4]) if status_vals[4] else None
    attempt_count = int(status_vals[5]) if status_vals[5] else 0
    permanently_failed = status_vals[6] == "1"

    # Determine overall status (priority order)
    if permanently_failed:
        overall_status = "permanently_failed"
    elif cancel_flag:
        overall_status = "cancelled"
    elif retry_phase_active and lock_exists:
        overall_status = "retry_in_progress"
    elif current_window >= total_windows and not lock_exists:
        overall_status = "complete"
    elif lock_exists:
        overall_status = "in_progress"
    else:
        overall_status = "pending"

    return {
        "overall_status": overall_status,
        "current_window": current_window,
        "total_windows": total_windows,
        "windows": windows,
        "summary": summary,
        "in_progress": overall_status in ("in_progress", "retry_in_progress"),
        # Phase 3 additions
        "retry_phase": retry_phase_active,
        "retry_type": retry_type,
        "retry_window": retry_window,
        "attempt_count": attempt_count,
        "max_attempts": GC_MAX_ATTEMPTS,
        "permanently_failed": permanently_failed,
    }


def get_pending_types(user_id: str | UUID) -> list[str]:
    """Get list of pending data types for a user."""
    user_id_str = str(user_id)
    pending = []

    for data_type in BACKFILL_DATA_TYPES:
        status = redis_client.get(_get_key(user_id_str, "types", data_type, "status"))
        if not status or status == "pending":
            pending.append(data_type)

    return pending


def mark_type_triggered(user_id: str | UUID, data_type: str) -> None:
    """Mark a data type as triggered (backfill request sent)."""
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


def mark_type_timed_out(user_id: str | UUID, data_type: str) -> int:
    """Mark a data type as timed_out (no webhook received within timeout).

    Returns:
        The new skip_count for this type (kept for diagnostics).
    """
    user_id_str = str(user_id)
    redis_client.setex(_get_key(user_id_str, "types", data_type, "status"), REDIS_TTL, "timed_out")

    # Increment skip count (persists across retries, used for diagnostics)
    skip_key = _get_key(user_id_str, "types", data_type, "skip_count")
    new_count = redis_client.incr(skip_key)
    redis_client.expire(skip_key, REDIS_TTL)

    trace_id = get_trace_id(user_id_str)
    type_trace_id = get_trace_id(user_id_str, data_type)
    log_structured(
        logger,
        "warning",
        "Marked type as timed_out (timeout)",
        provider="garmin",
        trace_id=trace_id,
        type_trace_id=type_trace_id,
        data_type=data_type,
        skip_count=new_count,
        user_id=user_id_str,
    )
    return new_count


# Backwards compatibility aliases
mark_type_skipped = mark_type_timed_out


def get_timed_out_types(user_id: str | UUID) -> list[str]:
    """Get list of timed_out data types for a user."""
    user_id_str = str(user_id)
    timed_out = []

    for data_type in BACKFILL_DATA_TYPES:
        status = redis_client.get(_get_key(user_id_str, "types", data_type, "status"))
        if status == "timed_out":
            timed_out.append(data_type)

    return timed_out


# Backwards compatibility aliases
get_skipped_types = get_timed_out_types


def get_type_skip_count(user_id: str | UUID, data_type: str) -> int:
    """Get the number of times a type has been skipped."""
    count = redis_client.get(_get_key(str(user_id), "types", data_type, "skip_count"))
    return int(count) if count else 0


def acquire_backfill_lock(user_id: str | UUID) -> bool:
    """Try to acquire exclusive backfill lock for a user.

    Returns True if lock acquired, False if already locked (backfill in progress).
    """
    lock_key = _get_key(str(user_id), "lock")
    return bool(redis_client.set(lock_key, "1", nx=True, ex=BACKFILL_LOCK_TTL))


def release_backfill_lock(user_id: str | UUID) -> None:
    """Release backfill lock."""
    redis_client.delete(_get_key(str(user_id), "lock"))


def set_cancel_flag(user_id: str | UUID) -> None:
    """Set cancel flag for a user's backfill."""
    redis_client.setex(_get_key(str(user_id), "cancel_flag"), REDIS_TTL, "1")


def is_cancelled(user_id: str | UUID) -> bool:
    """Check if backfill is cancelled."""
    return redis_client.get(_get_key(str(user_id), "cancel_flag")) == "1"


def clear_cancel_flag(user_id: str | UUID) -> None:
    """Clear cancel flag for a user's backfill."""
    redis_client.delete(_get_key(str(user_id), "cancel_flag"))


def record_timed_out_entry(user_id: str | UUID, data_type: str, window_idx: int) -> None:
    """Record a timed-out entry for Phase 3's end-of-run retry.

    Appends {"type": data_type, "window": window_idx} to a JSON list in Redis.
    """
    uid = str(user_id)
    key = _get_key(uid, "timed_out_types")

    existing = redis_client.get(key)
    entries: list[dict[str, Any]] = json.loads(existing) if existing else []
    entries.append({"type": data_type, "window": window_idx})
    redis_client.setex(key, REDIS_TTL, json.dumps(entries))


def get_retry_targets(user_id: str | UUID) -> list[dict[str, Any]]:
    """Get deduplicated retry targets from timed-out entries.

    Reads the timed_out_types JSON list from Redis, deduplicates to keep only
    the LATEST (highest) window per data type.

    Returns:
        List of {"type": str, "window": int} dicts, one per unique data type.
    """
    uid = str(user_id)
    key = _get_key(uid, "timed_out_types")

    raw = redis_client.get(key)
    if not raw:
        return []

    entries: list[dict[str, Any]] = json.loads(raw)
    if not entries:
        return []

    # Deduplicate: keep only the latest (highest) window per type
    latest: dict[str, int] = {}
    for entry in entries:
        dtype = entry["type"]
        window = entry["window"]
        if dtype not in latest or window > latest[dtype]:
            latest[dtype] = window

    return [{"type": dtype, "window": window} for dtype, window in latest.items()]


def is_retry_phase(user_id: str | UUID) -> bool:
    """Check if the backfill is currently in the retry phase."""
    return redis_client.get(_get_key(str(user_id), "retry_phase")) == "1"


def enter_retry_phase(user_id: str | UUID, retry_entries: list[dict[str, Any]]) -> None:
    """Enter the retry phase with the given retry targets.

    Sets the retry_phase flag and stores the list of targets to retry.
    """
    uid = str(user_id)

    redis_client.setex(_get_key(uid, "retry_phase"), REDIS_TTL, "1")
    redis_client.setex(_get_key(uid, "retry_targets"), REDIS_TTL, json.dumps(retry_entries))

    log_structured(
        logger,
        "info",
        "Entering retry phase",
        provider="garmin",
        user_id=uid,
        retry_target_count=len(retry_entries),
    )


def get_next_retry_target(user_id: str | UUID) -> dict[str, Any] | None:
    """Pop the next retry target from the retry_targets list.

    Returns:
        The next {"type": str, "window": int} entry, or None if empty/missing.
    """
    uid = str(user_id)
    key = _get_key(uid, "retry_targets")

    raw = redis_client.get(key)
    if not raw:
        return None

    targets: list[dict[str, Any]] = json.loads(raw)
    if not targets:
        return None

    entry = targets.pop(0)
    redis_client.setex(key, REDIS_TTL, json.dumps(targets))
    return entry


def setup_retry_window(user_id: str | UUID, window_idx: int) -> None:
    """Set the current retry window index in Redis."""
    uid = str(user_id)
    redis_client.setex(_get_key(uid, "retry_current_window"), REDIS_TTL, str(window_idx))


def get_window_date_range_for_index(user_id: str | UUID, window_idx: int) -> tuple[datetime, datetime]:
    """Get (start_time, end_time) for a specific window index.

    Same logic as get_window_date_range but takes an explicit window_idx
    instead of reading from window:current.

    Window N: anchor-(N+1)*chunk  ->  anchor-N*chunk
    """
    anchor = get_anchor_timestamp(user_id)
    chunk = BACKFILL_CHUNK_DAYS
    end_time = anchor - timedelta(days=window_idx * chunk)
    start_time = anchor - timedelta(days=(window_idx + 1) * chunk)
    return start_time, end_time


def update_window_cell(user_id: str | UUID, window_idx: int, data_type: str, status: str) -> None:
    """Write directly to a matrix cell for a specific window and data type.

    Used after retry completes (success or failure) to update the specific matrix cell.
    """
    uid = str(user_id)
    window_key = f"{REDIS_PREFIX}:{uid}:w:{window_idx}:{data_type}:status"
    redis_client.setex(window_key, REDIS_TTL, status)


def clear_retry_state(user_id: str | UUID) -> None:
    """Delete all retry-phase Redis keys."""
    uid = str(user_id)
    for suffix in ["retry_phase", "retry_targets", "retry_current_window", "retry_current_type"]:
        redis_client.delete(_get_key(uid, suffix))


def init_window_state(user_id: str | UUID, total_windows: int = BACKFILL_WINDOW_COUNT) -> None:
    """Initialize multi-window backfill state in Redis."""
    uid = str(user_id)
    anchor = datetime.now(timezone.utc).isoformat()
    redis_client.setex(_get_key(uid, "window", "current"), REDIS_TTL, "0")
    redis_client.setex(_get_key(uid, "window", "total"), REDIS_TTL, str(total_windows))
    redis_client.setex(_get_key(uid, "window", "anchor_ts"), REDIS_TTL, anchor)
    redis_client.setex(_get_key(uid, "window", "completed_count"), REDIS_TTL, "0")


def get_current_window(user_id: str | UUID) -> int:
    """Get current window index (0-indexed)."""
    val = redis_client.get(_get_key(str(user_id), "window", "current"))
    return int(val) if val else 0


def get_total_windows(user_id: str | UUID) -> int:
    """Get total number of windows for this backfill."""
    val = redis_client.get(_get_key(str(user_id), "window", "total"))
    return int(val) if val else BACKFILL_WINDOW_COUNT


def get_anchor_timestamp(user_id: str | UUID) -> datetime:
    """Get the fixed anchor timestamp for window calculation."""
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
    val = redis_client.get(_get_key(str(user_id), "window", "completed_count"))
    return int(val) if val else 0


def persist_window_results(user_id: str | UUID, window_idx: int) -> None:
    """Persist per-type results for a window to matrix keys.

    Maps flat orchestration status to matrix state:
    - "success" -> "done"
    - "timed_out" -> "timed_out"
    - "failed" -> "done" (Garmin error, treated as done at matrix level)
    - everything else -> "pending"
    """
    uid = str(user_id)
    results: dict[str, str] = {}
    keys = [_get_key(uid, "types", dt, "status") for dt in BACKFILL_DATA_TYPES]
    all_flat_statuses = redis_client.mget(keys)
    status_map = {"success": "done", "failed": "done", "timed_out": "timed_out"}

    for data_type, flat_status in zip(BACKFILL_DATA_TYPES, all_flat_statuses):
        matrix_status = status_map.get(flat_status, "pending")

        window_key = f"{REDIS_PREFIX}:{uid}:w:{window_idx}:{data_type}:status"
        redis_client.setex(window_key, REDIS_TTL, matrix_status)
        results[data_type] = matrix_status

    trace_id = get_trace_id(uid)
    log_structured(
        logger,
        "info",
        "Persisted window results to matrix keys",
        provider="garmin",
        trace_id=trace_id,
        user_id=uid,
        window=window_idx,
        results=results,
    )


def advance_window(user_id: str | UUID) -> bool:
    """Advance to next window. Returns True if more windows remain.

    Persists per-window matrix keys before resetting flat type keys.
    """
    uid = str(user_id)

    # Persist current window results to matrix keys BEFORE resetting
    current_window_before = get_current_window(uid)
    persist_window_results(uid, current_window_before)

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

    # Reset all backfill types to pending for the new window
    for data_type in BACKFILL_DATA_TYPES:
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
    user_id_str = str(user_id)

    # Set overall complete marker with shorter TTL (1 day)
    redis_client.setex(_get_key(user_id_str, "overall_complete"), 24 * 60 * 60, "1")

    # Release lock (belt-and-suspenders with trigger_next_pending_type finalization)
    release_backfill_lock(user_id_str)

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
    """Initialize and start full 365-day backfill (12 x 30-day windows) for all backfill data types.

    This is called after OAuth connection to auto-trigger historical sync.
    Triggers the first type and the rest will chain via webhooks.
    If existing state is detected (resume after cancel/crash), resumes from current window.

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

    # Reject re-trigger if permanently failed
    if redis_client.get(_get_key(user_id, "permanently_failed")) == "1":
        log_structured(
            logger,
            "warning",
            "Backfill permanently failed -- cannot re-trigger",
            provider="garmin",
            user_id=user_id,
        )
        return {
            "error": "Backfill permanently failed after maximum attempts. Disconnect and reconnect to reset.",
            "status": "permanently_failed",
        }

    # Acquire exclusive lock -- reject if already in progress
    if not acquire_backfill_lock(user_id):
        log_structured(
            logger,
            "warning",
            "Backfill already in progress",
            provider="garmin",
            user_id=user_id,
        )
        return {"error": "Backfill already in progress", "status": "rejected"}

    # Generate trace ID for this backfill session
    trace_id = set_trace_id(user_id)

    # Check for existing state (resume detection)
    current_window = get_current_window(user_id)
    cancel_flag = is_cancelled(user_id)

    if current_window > 0 or cancel_flag:
        # Resume from persisted state
        clear_cancel_flag(user_id)
        pending = get_pending_types(user_id)

        log_structured(
            logger,
            "info",
            "Resuming backfill from persisted state",
            provider="garmin",
            trace_id=trace_id,
            user_id=user_id,
            window=current_window,
            pending_types=pending,
        )

        if pending:
            trigger_backfill_for_type.apply_async(args=[user_id, pending[0]], countdown=1)
        else:
            trigger_next_pending_type.apply_async(args=[user_id], countdown=1)

        return {
            "status": "resumed",
            "user_id": user_id,
            "trace_id": trace_id,
            "window": current_window,
        }

    # Fresh start -- initialize window state and reset types
    init_window_state(user_id, total_windows=BACKFILL_WINDOW_COUNT)

    log_structured(
        logger,
        "info",
        "Starting full backfill",
        provider="garmin",
        trace_id=trace_id,
        user_id=user_id,
        total_types=len(BACKFILL_DATA_TYPES),
        total_windows=BACKFILL_WINDOW_COUNT,
        target_days=MAX_BACKFILL_DAYS,
    )

    # Reset all type statuses to pending
    for data_type in BACKFILL_DATA_TYPES:
        reset_type_status(user_id, data_type)

    # Trigger the first type (with small delay to avoid immediate burst)
    first_type = BACKFILL_DATA_TYPES[0]
    trigger_backfill_for_type.apply_async(args=[user_id, first_type], countdown=1)

    return {
        "status": "started",
        "user_id": user_id,
        "trace_id": trace_id,
        "total_types": len(BACKFILL_DATA_TYPES),
        "total_windows": BACKFILL_WINDOW_COUNT,
        "target_days": MAX_BACKFILL_DAYS,
        "first_type": first_type,
    }


@shared_task
def check_triggered_timeout(user_id: str, data_type: str) -> dict[str, Any]:
    """Check if a triggered type has timed out and mark it as timed_out.

    Scheduled by trigger_backfill_for_type with countdown=TRIGGERED_TIMEOUT_SECONDS.
    If the type is still "triggered" after the timeout, it means Garmin never sent
    a webhook (e.g., user has no data for this type).

    Args:
        user_id: UUID string of the user
        data_type: The data type to check

    Returns:
        Dict with timeout check result
    """
    user_id_str = str(user_id)
    trace_id = get_trace_id(user_id_str)
    type_trace_id = get_trace_id(user_id_str, data_type)

    # 0. Check cancel flag -- persist state and stop if cancelled
    if is_cancelled(user_id_str):
        current_window = get_current_window(user_id_str)
        persist_window_results(user_id_str, current_window)
        log_structured(
            logger,
            "info",
            "Timeout check: backfill cancelled, stopping",
            provider="garmin",
            trace_id=trace_id,
            type_trace_id=type_trace_id,
            data_type=data_type,
            user_id=user_id_str,
        )
        return {"status": "cancelled"}

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

    # 4. Mark as timed_out
    mark_type_timed_out(user_id_str, data_type)

    # During retry phase, a second timeout escalates to failed (per user decision)
    if is_retry_phase(user_id_str):
        mark_type_failed(user_id_str, data_type, "Timed out during retry (escalated to failed)")
        retry_window_str = redis_client.get(_get_key(user_id_str, "retry_current_window"))
        if retry_window_str:
            update_window_cell(user_id_str, int(retry_window_str), data_type, "failed")
    else:
        # Only record timed-out entry during initial run (not retry phase)
        record_timed_out_entry(user_id, data_type, get_current_window(user_id))

    # 5. Chain to next type
    trigger_next_pending_type.apply_async(args=[user_id], countdown=DELAY_BETWEEN_TYPES)

    skip_count = get_type_skip_count(user_id_str, data_type)
    return {
        "status": "timed_out",
        "data_type": data_type,
        "skip_count": skip_count,
        "action": "timed_out",
    }


@shared_task
def trigger_backfill_for_type(user_id: str, data_type: str) -> dict[str, Any]:
    """Trigger backfill for a specific data type.

    Args:
        user_id: UUID string of the user
        data_type: One of the backfill data types

    Returns:
        Dict with trigger status
    """
    if data_type not in BACKFILL_DATA_TYPES:
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

    # During retry phase, use the retry window's date range (not current sequential window)
    if is_retry_phase(user_id):
        retry_window_str = redis_client.get(_get_key(user_id, "retry_current_window"))
        if retry_window_str:
            start_time, end_time = get_window_date_range_for_index(user_id, int(retry_window_str))
            current_window = int(retry_window_str)
        else:
            start_time, end_time = get_window_date_range(user_id)
            current_window = get_current_window(user_id)
    else:
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
                        "warning",
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
                        "warning",
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

            # 409 duplicate — Garmin already processed this timeframe and won't
            # send another webhook.  Skip immediately to the next type instead
            # of waiting for the 5-min timeout.
            if data_type in result.get("duplicate", []):
                log_structured(
                    logger,
                    "info",
                    "Skipping duplicate backfill, proceeding to next type",
                    provider="garmin",
                    trace_id=trace_id,
                    type_trace_id=type_trace_id,
                    data_type=data_type,
                    user_id=user_id,
                )
                mark_type_success(user_id, data_type)
                trigger_next_pending_type.apply_async(args=[user_id], countdown=DELAY_BETWEEN_TYPES)
                return {
                    "status": "duplicate_skipped",
                    "data_type": data_type,
                    "start_date": start_time.isoformat(),
                    "end_date": end_time.isoformat(),
                }

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

            # 401 = token expired/revoked — all subsequent requests will also fail
            # 403 = user didn't grant HISTORICAL_DATA_EXPORT permission during OAuth
            # 400 "Endpoint not enabled" = app-level config issue in Garmin portal
            # All three cases affect all types identically, so stop the chain.
            is_endpoint_not_enabled = e.status_code == 400 and "endpoint not enabled" in error.lower()
            if e.status_code in (401, 403) or is_endpoint_not_enabled:
                if e.status_code == 401:
                    error_msg = "Authorization expired or revoked. Please re-authorize Garmin."
                    log_msg = "401: token invalid, stopping backfill for all types"
                elif is_endpoint_not_enabled:
                    error_msg = "Backfill endpoints not enabled for this app in Garmin developer portal."
                    log_msg = "Endpoint not enabled: stopping backfill for all types"
                else:
                    error_msg = "Historical data access not granted. User must re-authorize."
                    log_msg = "403: marking all remaining types as failed"
                log_structured(
                    logger,
                    "warning",
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
                    "warning",
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

    # Check cancel flag before proceeding
    if is_cancelled(user_id):
        current_window = get_current_window(user_id)
        persist_window_results(user_id, current_window)
        log_structured(
            logger,
            "info",
            "Backfill cancelled",
            provider="garmin",
            trace_id=trace_id,
            user_id=user_id,
        )
        return {"status": "cancelled"}

    pending_types = get_pending_types(user_id)

    if not pending_types:
        # During retry phase, handle retry target sequencing (not window advancement)
        if is_retry_phase(user_id):
            # Current retry type done. Check for more retry targets.
            # First, update the matrix cell for the just-completed retry
            retry_window_str = redis_client.get(_get_key(user_id, "retry_current_window"))
            retry_type_str = redis_client.get(_get_key(user_id, "retry_current_type"))
            if retry_window_str and retry_type_str:
                current_status = redis_client.get(_get_key(user_id, "types", retry_type_str, "status"))
                if current_status == "success":
                    update_window_cell(user_id, int(retry_window_str), retry_type_str, "done")
                elif current_status == "timed_out":
                    # Escalate to failed on second timeout (per user decision)
                    update_window_cell(user_id, int(retry_window_str), retry_type_str, "failed")
                    # Also mark flat status as failed for status API consistency
                    mark_type_failed(user_id, retry_type_str, "Timed out during retry (escalated to failed)")
                elif current_status == "failed":
                    update_window_cell(user_id, int(retry_window_str), retry_type_str, "failed")

            next_entry = get_next_retry_target(user_id)
            if next_entry:
                setup_retry_window(user_id, next_entry["window"])
                redis_client.setex(_get_key(user_id, "retry_current_type"), REDIS_TTL, next_entry["type"])
                reset_type_status(user_id, next_entry["type"])
                trigger_backfill_for_type.apply_async(
                    args=[user_id, next_entry["type"]],
                    countdown=DELAY_BETWEEN_TYPES,
                )
                log_structured(
                    logger,
                    "info",
                    "Retry phase: triggering next type",
                    provider="garmin",
                    trace_id=trace_id,
                    user_id=user_id,
                    retry_type=next_entry["type"],
                    retry_window=next_entry["window"],
                )
                return {"status": "retry_phase", "retrying": next_entry}

            # All retries done -- finalize
            clear_retry_state(user_id)
            release_backfill_lock(user_id)
            complete_backfill(user_id)
            log_structured(
                logger,
                "info",
                "Retry phase complete, backfill finalized",
                provider="garmin",
                trace_id=trace_id,
                user_id=user_id,
            )
            return {"status": "complete"}

        # No pending types -- current window done. Try advancing.
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
            first_type = BACKFILL_DATA_TYPES[0]
            trigger_backfill_for_type.apply_async(args=[user_id, first_type], countdown=DELAY_BETWEEN_TYPES)
            return {"status": "advancing_window", "window": current_window}

        # All windows exhausted -- check for retry phase
        retry_entries = get_retry_targets(user_id)
        if retry_entries and not is_retry_phase(user_id):
            # Enter retry phase
            enter_retry_phase(user_id, retry_entries)
            first_entry = get_next_retry_target(user_id)
            if first_entry:
                setup_retry_window(user_id, first_entry["window"])
                # Set retry_current_type so status API knows what's being retried
                redis_client.setex(
                    _get_key(user_id, "retry_current_type"),
                    REDIS_TTL,
                    first_entry["type"],
                )
                # Reset type status to pending for retry, then trigger
                reset_type_status(user_id, first_entry["type"])
                trigger_backfill_for_type.apply_async(
                    args=[user_id, first_entry["type"]],
                    countdown=DELAY_BETWEEN_TYPES,
                )
                log_structured(
                    logger,
                    "info",
                    "Retry phase: triggering first type",
                    provider="garmin",
                    trace_id=trace_id,
                    user_id=user_id,
                    retry_type=first_entry["type"],
                    retry_window=first_entry["window"],
                )
                return {"status": "retry_phase", "retrying": first_entry}

        # Retry phase done or no retries needed -- finalize
        clear_retry_state(user_id)
        release_backfill_lock(user_id)
        complete_backfill(user_id)
        completed_windows = get_completed_window_count(user_id)
        log_structured(
            logger,
            "info",
            "Backfill complete",
            provider="garmin",
            trace_id=trace_id,
            user_id=user_id,
            completed_windows=completed_windows,
        )
        return {"status": "complete", "completed_windows": completed_windows}

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
