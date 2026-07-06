"""Retry phase management: timed-out entries, retry queue, retry window state."""

import json
import logging
from typing import Any
from uuid import UUID

from app.integrations.redis_client import get_redis_client
from app.services.providers.garmin.backfill_config import REDIS_TTL
from app.services.providers.garmin.backfill_state.core import _get_key
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)


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
