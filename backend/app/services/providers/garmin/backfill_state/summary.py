"""Backfill completion and the overall status summary across windows and types."""

import logging
from typing import Any
from uuid import UUID

from app.integrations.redis_client import get_redis_client
from app.services.providers.garmin.backfill_config import BACKFILL_DATA_TYPES, REDIS_PREFIX
from app.services.providers.garmin.backfill_state.core import _get_key, get_trace_id, release_backfill_lock
from app.services.providers.garmin.backfill_state.window_state import (
    get_completed_window_count,
    get_current_window,
    get_total_windows,
)
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Completion
# ---------------------------------------------------------------------------


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
    """Return a full backfill status dict with per-window-per-type matrix."""
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
            window_states[dt] = state  # ty:ignore[invalid-assignment]
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
                "retry_phase",
                "retry_current_type",
                "retry_current_window",
            ]
        ]
    )

    lock_exists = status_vals[0] is not None
    retry_phase_active = status_vals[1] == "1"
    retry_type = status_vals[2]
    retry_window = int(status_vals[3]) if status_vals[3] else None

    if retry_phase_active and lock_exists:
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
    }
