"""Celery periodic task for detecting and clearing stuck Garmin backfills.

Without GC, a stuck backfill (lost Celery task, crash, network partition) blocks
the user forever until the 6-hour lock TTL expires. The GC detects stuck backfills
within ~13 minutes (10-min threshold + 3-min scan interval) and clears them so the
user can re-trigger.

Flow:
1. gc_stuck_backfills() scans all backfill lock keys via SCAN
2. For each locked user, is_stuck() checks if any activity happened recently
3. clear_stuck_backfill() releases the lock, marks the triggered type as timed_out,
   increments the attempt counter, and sets permanently_failed after 3 attempts
"""

from datetime import datetime, timezone
from logging import getLogger
from typing import Any

from app.integrations.redis_client import get_redis_client
from app.services.providers.garmin.backfill_config import (
    BACKFILL_DATA_TYPES,
    GC_MAX_ATTEMPTS,
    GC_STUCK_THRESHOLD_SECONDS,
    REDIS_PREFIX,
    REDIS_TTL,
)
from app.utils.structured_logging import log_structured
from celery import shared_task

from .garmin_backfill_task import (
    get_current_window,
    is_retry_phase,
    mark_type_timed_out,
    record_timed_out_entry,
    release_backfill_lock,
)

logger = getLogger(__name__)


def _key(user_id: str, *parts: str) -> str:
    """Generate Redis key for backfill tracking."""
    return ":".join([REDIS_PREFIX, user_id, *parts])


def is_stuck(user_id: str, threshold_seconds: int = GC_STUCK_THRESHOLD_SECONDS) -> bool:
    """Check if a backfill has had NO activity for threshold_seconds.

    Looks at triggered_at and completed_at timestamps for ALL BACKFILL_DATA_TYPES
    in the current window's flat keys. Also checks anchor_ts as fallback (backfill
    started but no types triggered yet).

    Returns True only if the MOST RECENT timestamp across all types is older than
    the threshold. If no timestamps exist at all, returns True (orphaned lock).
    """
    redis_client = get_redis_client()
    now = datetime.now(timezone.utc)

    most_recent: datetime | None = None

    # Check triggered_at and completed_at for each data type
    for data_type in BACKFILL_DATA_TYPES:
        for suffix in ("triggered_at", "completed_at"):
            val = redis_client.get(_key(user_id, "types", data_type, suffix))
            if val:
                try:
                    ts = datetime.fromisoformat(val)
                    if most_recent is None or ts > most_recent:
                        most_recent = ts
                except (ValueError, TypeError):
                    continue

    # Fallback: check anchor_ts (set when backfill starts, before any type is triggered)
    anchor_val = redis_client.get(_key(user_id, "window", "anchor_ts"))
    if anchor_val:
        try:
            anchor_ts = datetime.fromisoformat(anchor_val)
            if most_recent is None or anchor_ts > most_recent:
                most_recent = anchor_ts
        except (ValueError, TypeError):
            pass

    # No timestamps at all = orphaned lock
    if most_recent is None:
        return True

    elapsed = (now - most_recent).total_seconds()
    return elapsed >= threshold_seconds


def clear_stuck_backfill(user_id: str) -> dict[str, Any]:
    """Clear a stuck backfill: release lock, mark triggered type as timed_out, track attempts.

    Preserves completed window data -- only clears the lock and marks the
    currently-triggered type. Increments attempt counter; after GC_MAX_ATTEMPTS
    the backfill is marked permanently failed.

    Returns:
        Dict with user_id, attempt_count, permanently_failed, cleared_type.
    """
    redis_client = get_redis_client()

    # Increment attempt counter
    attempt_key = _key(user_id, "attempt_count")
    attempt_count = redis_client.incr(attempt_key)
    redis_client.expire(attempt_key, REDIS_TTL)

    # Find the currently-triggered type
    cleared_type: str | None = None
    for data_type in BACKFILL_DATA_TYPES:
        status = redis_client.get(_key(user_id, "types", data_type, "status"))
        if status == "triggered":
            cleared_type = data_type
            break

    # Mark the triggered type as timed_out and record for retry
    if cleared_type:
        mark_type_timed_out(user_id, cleared_type)
        current_window = get_current_window(user_id)
        record_timed_out_entry(user_id, cleared_type, current_window)

    # Release the backfill lock (preserves all completed window data)
    release_backfill_lock(user_id)

    # Check if permanently failed
    permanently_failed = attempt_count >= GC_MAX_ATTEMPTS
    if permanently_failed:
        pf_key = _key(user_id, "permanently_failed")
        redis_client.setex(pf_key, REDIS_TTL, "1")

    log_structured(
        logger,
        "warning",
        "GC cleared stuck backfill",
        provider="garmin",
        user_id=user_id,
        attempt_count=attempt_count,
        max_attempts=GC_MAX_ATTEMPTS,
        cleared_type=cleared_type,
        permanently_failed=permanently_failed,
    )

    return {
        "user_id": user_id,
        "attempt_count": attempt_count,
        "permanently_failed": permanently_failed,
        "cleared_type": cleared_type,
    }


@shared_task
def gc_stuck_backfills() -> dict[str, Any]:
    """Periodic task: scan for stuck Garmin backfills and clear them.

    Uses Redis SCAN to find all backfill lock keys, then checks each for
    stuck state. Skips users in active retry phase to avoid interference.

    Returns:
        Dict with cleared user_ids, scanned flag, and total locks checked.
    """
    redis_client = get_redis_client()
    match_pattern = f"{REDIS_PREFIX}:*:lock"

    log_structured(
        logger,
        "debug",
        "GC scan starting",
        provider="garmin",
        match_pattern=match_pattern,
    )

    cleared: list[str] = []
    total_locks_checked = 0
    cursor = 0

    while True:
        cursor, keys = redis_client.scan(cursor=cursor, match=match_pattern, count=100)

        for key in keys:
            # key format: "garmin:backfill:{user_id}:lock"
            # Handle both bytes and str from Redis
            key_str = key if isinstance(key, str) else key.decode("utf-8")
            parts = key_str.split(":")
            if len(parts) < 4:
                continue

            user_id = parts[2]
            total_locks_checked += 1

            # Skip users in active retry phase
            if is_retry_phase(user_id):
                continue

            # Skip if backfill is actively progressing
            if not is_stuck(user_id):
                continue

            result = clear_stuck_backfill(user_id)
            cleared.append(user_id)

            log_structured(
                logger,
                "warning",
                "GC cleared stuck backfill for user",
                provider="garmin",
                user_id=user_id,
                attempt_count=result["attempt_count"],
                permanently_failed=result["permanently_failed"],
                cleared_type=result["cleared_type"],
            )

        if cursor == 0:
            break

    if not cleared:
        log_structured(
            logger,
            "debug",
            "GC scan complete, no stuck backfills found",
            provider="garmin",
            total_locks_checked=total_locks_checked,
        )

    return {
        "cleared": cleared,
        "scanned": True,
        "total_locks_checked": total_locks_checked,
    }
