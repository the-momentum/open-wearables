"""Garmin backfill Redis state management.

Pure Redis key operations for tracking per-user backfill progress.
No Celery, no HTTP, no database — consumed by both the Celery task
orchestrator (garmin_backfill_task) and the webhook handler.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from app.integrations.redis_client import get_redis_client
from app.services.providers.garmin.backfill_config import (
    BACKFILL_CHUNK_DAYS,
    BACKFILL_DATA_TYPES,
    BACKFILL_LOCK_TTL,
    BACKFILL_WINDOW_COUNT,
    GC_MAX_ATTEMPTS,
    REDIS_PREFIX,
    REDIS_TTL,
)
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)


def _get_key(user_id: str | UUID, *parts: str) -> str:
    """Generate a namespaced Redis key for backfill tracking."""
    return ":".join([REDIS_PREFIX, str(user_id), *parts])


# ---------------------------------------------------------------------------
# Trace IDs
# ---------------------------------------------------------------------------


def set_trace_id(user_id: str | UUID) -> str:
    """Generate and store a session-level trace ID for a user's backfill."""
    trace_id = str(uuid4())[:8]
    get_redis_client().setex(_get_key(user_id, "trace_id"), REDIS_TTL, trace_id)
    return trace_id


def get_trace_id(user_id: str | UUID, data_type: str | None = None) -> str | None:
    """Return the active backfill trace ID for a user, optionally per-type."""
    if data_type:
        return get_redis_client().get(_get_key(user_id, "types", data_type, "trace_id"))
    return get_redis_client().get(_get_key(user_id, "trace_id"))


def set_type_trace_id(user_id: str | UUID, data_type: str) -> str:
    """Generate and store a per-type trace ID for a specific backfill data type."""
    trace_id = str(uuid4())[:8]
    get_redis_client().setex(_get_key(user_id, "types", data_type, "trace_id"), REDIS_TTL, trace_id)
    return trace_id


# ---------------------------------------------------------------------------
# Per-type status
# ---------------------------------------------------------------------------


def get_pending_types(user_id: str | UUID) -> list[str]:
    """Return data types whose status is pending (not yet triggered)."""
    user_id_str = str(user_id)
    return [
        dt
        for dt in BACKFILL_DATA_TYPES
        if not get_redis_client().get(_get_key(user_id_str, "types", dt, "status"))
        or get_redis_client().get(_get_key(user_id_str, "types", dt, "status")) == "pending"
    ]


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


# Backwards compatibility alias
mark_type_skipped = mark_type_timed_out


def get_timed_out_types(user_id: str | UUID) -> list[str]:
    """Return data types whose status is timed_out."""
    user_id_str = str(user_id)
    return [
        dt
        for dt in BACKFILL_DATA_TYPES
        if get_redis_client().get(_get_key(user_id_str, "types", dt, "status")) == "timed_out"
    ]


# Backwards compatibility alias
get_skipped_types = get_timed_out_types


def get_type_skip_count(user_id: str | UUID, data_type: str) -> int:
    """Return the number of times a type has been skipped/timed-out."""
    count = get_redis_client().get(_get_key(str(user_id), "types", data_type, "skip_count"))
    return int(count) if count else 0


# ---------------------------------------------------------------------------
# Lock
# ---------------------------------------------------------------------------


def acquire_backfill_lock(user_id: str | UUID) -> bool:
    """Try to acquire exclusive backfill lock.

    Returns True if the lock was acquired, False if already locked.
    """
    lock_key = _get_key(str(user_id), "lock")
    return bool(get_redis_client().set(lock_key, "1", nx=True, ex=BACKFILL_LOCK_TTL))


def release_backfill_lock(user_id: str | UUID) -> None:
    """Release the backfill lock."""
    get_redis_client().delete(_get_key(str(user_id), "lock"))


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------


def set_cancel_flag(user_id: str | UUID) -> None:
    """Set the cancel flag for a user's backfill."""
    get_redis_client().setex(_get_key(str(user_id), "cancel_flag"), REDIS_TTL, "1")


def is_cancelled(user_id: str | UUID) -> bool:
    """Return True if the backfill cancel flag is set."""
    return get_redis_client().get(_get_key(str(user_id), "cancel_flag")) == "1"


def clear_cancel_flag(user_id: str | UUID) -> None:
    """Clear the backfill cancel flag."""
    get_redis_client().delete(_get_key(str(user_id), "cancel_flag"))


# ---------------------------------------------------------------------------
# Timed-out entries (for Phase-3 retry)
# ---------------------------------------------------------------------------


def record_timed_out_entry(user_id: str | UUID, data_type: str, window_idx: int) -> None:
    """Append a timed-out entry to the JSON list used by Phase-3 retry."""
    uid = str(user_id)
    key = _get_key(uid, "timed_out_types")
    existing = get_redis_client().get(key)
    entries: list[dict[str, Any]] = json.loads(existing) if existing else []
    entries.append({"type": data_type, "window": window_idx})
    get_redis_client().setex(key, REDIS_TTL, json.dumps(entries))


def get_retry_targets(user_id: str | UUID) -> list[dict[str, Any]]:
    """Return deduplicated retry targets, keeping the latest window per type."""
    uid = str(user_id)
    raw = get_redis_client().get(_get_key(uid, "timed_out_types"))
    if not raw:
        return []
    entries: list[dict[str, Any]] = json.loads(raw)
    if not entries:
        return []
    latest: dict[str, int] = {}
    for entry in entries:
        dtype, window = entry["type"], entry["window"]
        if dtype not in latest or window > latest[dtype]:
            latest[dtype] = window
    return [{"type": dtype, "window": window} for dtype, window in latest.items()]


# ---------------------------------------------------------------------------
# Retry phase
# ---------------------------------------------------------------------------


def is_retry_phase(user_id: str | UUID) -> bool:
    """Return True if the backfill is currently in the retry phase."""
    return get_redis_client().get(_get_key(str(user_id), "retry_phase")) == "1"


def enter_retry_phase(user_id: str | UUID, retry_entries: list[dict[str, Any]]) -> None:
    """Enter retry phase with the given retry targets."""
    uid = str(user_id)
    get_redis_client().setex(_get_key(uid, "retry_phase"), REDIS_TTL, "1")
    get_redis_client().setex(_get_key(uid, "retry_targets"), REDIS_TTL, json.dumps(retry_entries))

    log_structured(
        logger,
        "info",
        "Entering retry phase",
        provider="garmin",
        user_id=uid,
        retry_target_count=len(retry_entries),
    )


def get_next_retry_target(user_id: str | UUID) -> dict[str, Any] | None:
    """Pop and return the next retry target, or None if the queue is empty."""
    uid = str(user_id)
    key = _get_key(uid, "retry_targets")
    raw = get_redis_client().get(key)
    if not raw:
        return None
    targets: list[dict[str, Any]] = json.loads(raw)
    if not targets:
        return None
    entry = targets.pop(0)
    get_redis_client().setex(key, REDIS_TTL, json.dumps(targets))
    return entry


def setup_retry_window(user_id: str | UUID, window_idx: int) -> None:
    """Set the current retry window index in Redis."""
    uid = str(user_id)
    get_redis_client().setex(_get_key(uid, "retry_current_window"), REDIS_TTL, str(window_idx))


def clear_retry_state(user_id: str | UUID) -> None:
    """Delete all retry-phase Redis keys."""
    uid = str(user_id)
    for suffix in ["retry_phase", "retry_targets", "retry_current_window", "retry_current_type"]:
        get_redis_client().delete(_get_key(uid, suffix))


# ---------------------------------------------------------------------------
# Window state
# ---------------------------------------------------------------------------


def init_window_state(user_id: str | UUID, total_windows: int = BACKFILL_WINDOW_COUNT) -> None:
    """Initialise multi-window backfill state in Redis."""
    uid = str(user_id)
    anchor = datetime.now(timezone.utc).isoformat()
    get_redis_client().setex(_get_key(uid, "window", "current"), REDIS_TTL, "0")
    get_redis_client().setex(_get_key(uid, "window", "total"), REDIS_TTL, str(total_windows))
    get_redis_client().setex(_get_key(uid, "window", "anchor_ts"), REDIS_TTL, anchor)
    get_redis_client().setex(_get_key(uid, "window", "completed_count"), REDIS_TTL, "0")


def get_current_window(user_id: str | UUID) -> int:
    """Return the current window index (0-indexed)."""
    val = get_redis_client().get(_get_key(str(user_id), "window", "current"))
    return int(val) if val else 0


def get_total_windows(user_id: str | UUID) -> int:
    """Return the total number of windows for this backfill."""
    val = get_redis_client().get(_get_key(str(user_id), "window", "total"))
    return int(val) if val else BACKFILL_WINDOW_COUNT


def get_anchor_timestamp(user_id: str | UUID) -> datetime:
    """Return the fixed anchor timestamp used for window date calculation."""
    val = get_redis_client().get(_get_key(str(user_id), "window", "anchor_ts"))
    if val:
        return datetime.fromisoformat(val)
    return datetime.now(timezone.utc)


def get_window_date_range(user_id: str | UUID) -> tuple[datetime, datetime]:
    """Return (start_time, end_time) for the current window.

    Window 0: anchor-30d → anchor
    Window N: anchor-(N+1)*30d → anchor-N*30d
    """
    anchor = get_anchor_timestamp(user_id)
    window = get_current_window(user_id)
    chunk = BACKFILL_CHUNK_DAYS
    end_time = anchor - timedelta(days=window * chunk)
    start_time = anchor - timedelta(days=(window + 1) * chunk)
    return start_time, end_time


def get_window_date_range_for_index(user_id: str | UUID, window_idx: int) -> tuple[datetime, datetime]:
    """Return (start_time, end_time) for an explicit window index."""
    anchor = get_anchor_timestamp(user_id)
    chunk = BACKFILL_CHUNK_DAYS
    end_time = anchor - timedelta(days=window_idx * chunk)
    start_time = anchor - timedelta(days=(window_idx + 1) * chunk)
    return start_time, end_time


def get_completed_window_count(user_id: str | UUID) -> int:
    """Return the number of completed windows."""
    val = get_redis_client().get(_get_key(str(user_id), "window", "completed_count"))
    return int(val) if val else 0


def update_window_cell(user_id: str | UUID, window_idx: int, data_type: str, status: str) -> None:
    """Write directly to a matrix cell (used after retry completes)."""
    uid = str(user_id)
    window_key = f"{REDIS_PREFIX}:{uid}:w:{window_idx}:{data_type}:status"
    get_redis_client().setex(window_key, REDIS_TTL, status)


def persist_window_results(user_id: str | UUID, window_idx: int) -> None:
    """Persist per-type results for a window to matrix keys.

    Maps orchestration status → matrix state:
    - "success" / "failed" → "done"
    - "timed_out" → "timed_out"
    - everything else → "pending"
    """
    uid = str(user_id)
    results: dict[str, str] = {}
    keys = [_get_key(uid, "types", dt, "status") for dt in BACKFILL_DATA_TYPES]
    all_flat_statuses = get_redis_client().mget(keys)
    status_map = {"success": "done", "failed": "done", "timed_out": "timed_out"}

    for data_type, flat_status in zip(BACKFILL_DATA_TYPES, all_flat_statuses):
        matrix_status = status_map.get(flat_status, "pending")
        window_key = f"{REDIS_PREFIX}:{uid}:w:{window_idx}:{data_type}:status"
        get_redis_client().setex(window_key, REDIS_TTL, matrix_status)
        results[data_type] = matrix_status

    log_structured(
        logger,
        "info",
        "Persisted window results to matrix keys",
        provider="garmin",
        trace_id=get_trace_id(uid),
        user_id=uid,
        window=window_idx,
        results=results,
    )


def advance_window(user_id: str | UUID) -> bool:
    """Advance to the next window. Returns True if more windows remain."""
    uid = str(user_id)
    current_window_before = get_current_window(uid)
    persist_window_results(uid, current_window_before)

    completed_key = _get_key(uid, "window", "completed_count")
    get_redis_client().incr(completed_key)
    get_redis_client().expire(completed_key, REDIS_TTL)

    current_key = _get_key(uid, "window", "current")
    new_window = get_redis_client().incr(current_key)
    get_redis_client().expire(current_key, REDIS_TTL)

    total = get_total_windows(uid)
    if new_window >= total:
        return False

    for data_type in BACKFILL_DATA_TYPES:
        reset_type_status(uid, data_type)
        get_redis_client().delete(_get_key(uid, "types", data_type, "skip_count"))

    log_structured(
        logger,
        "info",
        "Advanced to next backfill window",
        provider="garmin",
        trace_id=get_trace_id(uid),
        user_id=uid,
        window=new_window,
        total_windows=total,
    )
    return True


def complete_backfill(user_id: str | UUID) -> None:
    """Mark the entire backfill as complete."""
    user_id_str = str(user_id)
    get_redis_client().setex(_get_key(user_id_str, "overall_complete"), 24 * 60 * 60, "1")
    release_backfill_lock(user_id_str)

    log_structured(
        logger,
        "info",
        "Completed full backfill",
        provider="garmin",
        trace_id=get_trace_id(user_id_str),
        user_id=user_id_str,
        completed_windows=get_completed_window_count(user_id_str),
    )


# ---------------------------------------------------------------------------
# Overall status summary
# ---------------------------------------------------------------------------


def get_backfill_status(user_id: str | UUID) -> dict[str, Any]:
    """Return a full backfill status dict with per-window-per-type matrix.

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

    for w in range(current_window):
        window_states: dict[str, str] = {}
        for dt in BACKFILL_DATA_TYPES:
            key = f"{REDIS_PREFIX}:{uid}:w:{w}:{dt}:status"
            state = get_redis_client().get(key) or "pending"
            window_states[dt] = state
            if state in summary[dt]:
                summary[dt][state] += 1
        windows[str(w)] = window_states

    current_states: dict[str, str] = {}
    for dt in BACKFILL_DATA_TYPES:
        flat_status = get_redis_client().get(_get_key(uid, "types", dt, "status"))
        match flat_status:
            case "success":
                state = "done"
            case "timed_out" | "failed":
                state = str(flat_status)
            case "pending" | "triggered" | None:
                state = "pending"
            case _:
                state = str(flat_status)
        current_states[dt] = state
        if state in summary[dt]:
            summary[dt][state] += 1
    windows[str(current_window)] = current_states

    status_vals = get_redis_client().mget(
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
        "retry_phase": retry_phase_active,
        "retry_type": retry_type,
        "retry_window": retry_window,
        "attempt_count": attempt_count,
        "max_attempts": GC_MAX_ATTEMPTS,
        "permanently_failed": permanently_failed,
    }
