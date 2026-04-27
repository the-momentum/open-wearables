"""Core backfill state: Redis key helper, trace IDs, lock, cancellation, completion, status."""

import logging
from typing import Any
from uuid import UUID, uuid4

from app.integrations.redis_client import get_redis_client
from app.services.providers.garmin.backfill_config import (
    BACKFILL_DATA_TYPES,
    BACKFILL_LOCK_TTL,
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
# Lock
# ---------------------------------------------------------------------------


def acquire_backfill_lock(user_id: str | UUID) -> str | None:
    """Try to acquire exclusive backfill lock.

    Returns a unique token string on success, or None if already locked.
    The token is also persisted in Redis so cross-task release is possible.
    """
    uid = str(user_id)
    token = uuid4().hex
    lock_key = _get_key(uid, "lock")
    acquired = bool(get_redis_client().set(lock_key, token, nx=True, ex=BACKFILL_LOCK_TTL))
    if acquired:
        get_redis_client().setex(_get_key(uid, "lock_token"), BACKFILL_LOCK_TTL, token)
    return token if acquired else None


_RELEASE_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""


def release_backfill_lock(user_id: str | UUID, token: str | None = None) -> bool:
    """Atomically release the backfill lock if it still belongs to the caller.

    If *token* is omitted the stored companion key is used (enables cross-task
    release where the original token was not threaded through).  Returns True
    when the lock was actually deleted.
    """
    uid = str(user_id)
    lock_key = _get_key(uid, "lock")
    token_key = _get_key(uid, "lock_token")
    if token is None:
        token = get_redis_client().get(token_key)
    if not token:
        return False
    result = bool(get_redis_client().eval(_RELEASE_LUA, 1, lock_key, token))
    get_redis_client().delete(token_key)
    return result


def force_release_backfill_lock(user_id: str | UUID) -> None:
    """Unconditionally release the backfill lock — use only from GC / admin paths."""
    uid = str(user_id)
    get_redis_client().delete(_get_key(uid, "lock"), _get_key(uid, "lock_token"))


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
# Completion
# ---------------------------------------------------------------------------


def complete_backfill(user_id: str | UUID) -> None:
    """Mark the entire backfill as complete."""
    from app.services.providers.garmin.backfill_state.window_state import get_completed_window_count

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
    """Return a full backfill status dict with per-window-per-type matrix."""
    from app.services.providers.garmin.backfill_state.window_state import (
        get_current_window,
        get_total_windows,
    )

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

    if current_window < total_windows:
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
