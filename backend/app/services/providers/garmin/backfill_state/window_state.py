"""Multi-window backfill state: init, advance, date ranges, matrix persistence."""

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.integrations.redis_client import get_redis_client
from app.services.providers.garmin.backfill_config import (
    BACKFILL_CHUNK_DAYS,
    BACKFILL_DATA_TYPES,
    BACKFILL_WINDOW_COUNT,
    REDIS_PREFIX,
    REDIS_TTL,
)
from app.services.providers.garmin.backfill_state.core import _get_key, get_trace_id
from app.services.providers.garmin.backfill_state.type_tracking import reset_type_status
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)


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
