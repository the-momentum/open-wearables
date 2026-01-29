"""Celery task for Garmin REST Summary Sync.

This task manages the fetching of 7 days of recent Garmin data using
REST Summary endpoints with rate-limited, chunked requests.

Unlike the backfill approach (async webhook-based), this directly fetches
data via HTTP and persists it immediately.

For historical data beyond 7 days, use the backfill service (webhook-based).

Flow: Start → Chunk 1 (dailies day 0) → delay → Chunk 2 (dailies day 1) → ... → Complete
"""

import json
from datetime import datetime, timedelta, timezone
from logging import getLogger
from typing import Any
from uuid import UUID

from app.database import SessionLocal
from app.integrations.redis_client import get_redis_client
from celery import Task, shared_task

logger = getLogger(__name__)

# Redis key prefix for summary sync tracking
REDIS_PREFIX = "garmin:summary"

# Target days of historical data (7 days for summary, beyond that use backfill)
TARGET_DAYS = 7

# Chunk size in hours (Garmin API limit)
CHUNK_SIZE_HOURS = 24

# Rate limiting delays (seconds)
DEFAULT_CHUNK_DELAY = 180  # 3 minutes (within 2-5 min range)
HRV_CHUNK_DELAY = 600  # 10 minutes (HRV is rate-limit sensitive)
ACTIVITY_DETAILS_DELAY = 300  # 5 minutes (data-heavy)

# Data types in priority order (most important first, rate-sensitive last)
DATA_TYPES = [
    "dailies",
    "sleeps",
    "activities",
    "epochs",
    "stressDetails",
    "respiration",
    "pulseOx",
    "bodyComps",
    "bloodPressures",
    "userMetrics",
    "skinTemp",
    "healthSnapshot",
    "moveiq",
    "mct",
    "hrv",  # HRV last (most rate-sensitive)
    "activityDetails",  # Last (most data-heavy)
]

# Rate-sensitive endpoints that need longer delays
RATE_SENSITIVE_TYPES: dict[str, int] = {
    "hrv": HRV_CHUNK_DELAY,
    "activityDetails": ACTIVITY_DETAILS_DELAY,
}

# Maximum number of errors to store
MAX_ERRORS = 10


def _get_sync_key(user_id: str | UUID, key_type: str) -> str:
    """Generate Redis key for sync tracking."""
    return f"{REDIS_PREFIX}:{user_id}:{key_type}"


def get_sync_status(user_id: str | UUID) -> dict[str, Any]:
    """Get current summary sync status for a user.

    Returns:
        {
            "status": "IDLE" | "SYNCING" | "WAITING" | "COMPLETED" | "FAILED",
            "progress_percent": float,
            "current_data_type": str,
            "current_type_index": int,
            "total_types": int,
            "current_day": int,
            "target_days": int,
            "started_at": str | None,
            "last_chunk_at": str | None,
            "errors": list[dict]
        }
    """
    redis_client = get_redis_client()

    status = redis_client.get(_get_sync_key(user_id, "status"))
    type_index = redis_client.get(_get_sync_key(user_id, "type_index"))
    current_day = redis_client.get(_get_sync_key(user_id, "current_day"))
    started_at = redis_client.get(_get_sync_key(user_id, "started_at"))
    last_chunk_at = redis_client.get(_get_sync_key(user_id, "last_chunk_at"))
    errors_json = redis_client.get(_get_sync_key(user_id, "errors"))

    # Parse values
    type_idx = int(type_index) if type_index else 0
    day = int(current_day) if current_day else 0

    # Ensure type_idx is within bounds
    if type_idx >= len(DATA_TYPES):
        type_idx = len(DATA_TYPES) - 1

    # Parse errors
    errors: list[dict[str, Any]] = []
    if errors_json:
        try:
            errors = json.loads(errors_json)
        except json.JSONDecodeError:
            errors = []

    # Calculate progress
    total_chunks = TARGET_DAYS * len(DATA_TYPES)
    completed_chunks = (type_idx * TARGET_DAYS) + day
    progress_percent = (completed_chunks / total_chunks * 100) if total_chunks > 0 else 0

    return {
        "status": status or "IDLE",
        "progress_percent": round(progress_percent, 1),
        "current_data_type": DATA_TYPES[type_idx] if type_idx < len(DATA_TYPES) else "complete",
        "current_type_index": type_idx,
        "total_types": len(DATA_TYPES),
        "current_day": day,
        "target_days": TARGET_DAYS,
        "started_at": started_at,
        "last_chunk_at": last_chunk_at,
        "errors": errors[-MAX_ERRORS:],  # Return only recent errors
    }


def start_sync(user_id: str | UUID, resume: bool = False) -> dict[str, Any]:
    """Initialize or resume summary sync tracking for a user.

    Args:
        user_id: User UUID
        resume: If True, resume from last position; otherwise start fresh

    Returns:
        Dict with initial status
    """
    redis_client = get_redis_client()

    # Check if already syncing
    current_status = redis_client.get(_get_sync_key(user_id, "status"))
    if current_status in ("SYNCING", "WAITING"):
        if not resume:
            return {
                "error": "Sync already in progress",
                "status": current_status,
            }
        # Resume: keep current position
        logger.info(f"Resuming summary sync for user {user_id}")
    else:
        # Fresh start: reset position
        redis_client.set(_get_sync_key(user_id, "type_index"), "0")
        redis_client.set(_get_sync_key(user_id, "current_day"), "0")
        redis_client.delete(_get_sync_key(user_id, "errors"))
        logger.info(f"Starting fresh summary sync for user {user_id}")

    now = datetime.now(timezone.utc).isoformat()

    redis_client.set(_get_sync_key(user_id, "status"), "SYNCING")
    redis_client.set(_get_sync_key(user_id, "started_at"), now)

    # Set TTL of 7 days to auto-cleanup stale syncs
    ttl = 7 * 24 * 3600
    for key_type in ["status", "type_index", "current_day", "started_at", "last_chunk_at", "errors"]:
        redis_client.expire(_get_sync_key(user_id, key_type), ttl)

    return get_sync_status(user_id)


def cancel_sync(user_id: str | UUID) -> dict[str, Any]:
    """Cancel an in-progress sync and clean up Redis keys.

    Args:
        user_id: User UUID

    Returns:
        Dict with cancellation status
    """
    redis_client = get_redis_client()

    current_status = redis_client.get(_get_sync_key(user_id, "status"))
    if current_status not in ("SYNCING", "WAITING"):
        return {"cancelled": False, "message": "No sync in progress"}

    # Mark as idle (cancelled)
    redis_client.set(_get_sync_key(user_id, "status"), "IDLE")

    logger.info(f"Cancelled summary sync for user {user_id}")
    return {"cancelled": True, "message": "Sync cancelled"}


def _add_error(user_id: str | UUID, data_type: str, day: int, error: str) -> None:
    """Add an error to the error list in Redis."""
    redis_client = get_redis_client()

    errors_json = redis_client.get(_get_sync_key(user_id, "errors"))
    errors: list[dict[str, Any]] = []
    if errors_json:
        try:
            errors = json.loads(errors_json)
        except json.JSONDecodeError:
            errors = []

    errors.append(
        {
            "data_type": data_type,
            "day": day,
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )

    # Keep only recent errors
    errors = errors[-MAX_ERRORS:]
    redis_client.set(_get_sync_key(user_id, "errors"), json.dumps(errors))


def _complete_sync(user_id: str | UUID) -> None:
    """Mark sync as completed."""
    redis_client = get_redis_client()
    redis_client.set(_get_sync_key(user_id, "status"), "COMPLETED")
    # Keep completed status for 1 day
    redis_client.expire(_get_sync_key(user_id, "status"), 86400)
    logger.info(f"Completed summary sync for user {user_id}")


def _get_chunk_delay(data_type: str) -> int:
    """Get the appropriate delay for a data type."""
    return RATE_SENSITIVE_TYPES.get(data_type, DEFAULT_CHUNK_DELAY)


@shared_task(bind=True, max_retries=3)
def process_garmin_summary_chunk(self: Task, user_id: str) -> dict[str, Any]:
    """Process a single chunk of Garmin summary data.

    This task:
    1. Fetches one 24-hour chunk of data
    2. Saves it to the database
    3. Updates progress in Redis
    4. Schedules the next chunk with appropriate delay

    Args:
        user_id: UUID string of the user

    Returns:
        Dict with processing results
    """
    redis_client = get_redis_client()

    try:
        user_uuid = UUID(user_id)
    except ValueError as e:
        logger.error(f"Invalid user_id: {user_id}")
        return {"error": f"Invalid user_id: {e}"}

    # Check if sync is still active
    current_status = redis_client.get(_get_sync_key(user_id, "status"))
    if current_status not in ("SYNCING", "WAITING"):
        logger.info(f"Sync not active for user {user_id} (status: {current_status}), stopping")
        return {"status": "cancelled"}

    # Get current position
    type_index = int(redis_client.get(_get_sync_key(user_id, "type_index")) or "0")
    current_day = int(redis_client.get(_get_sync_key(user_id, "current_day")) or "0")

    # Check if all data types are complete
    if type_index >= len(DATA_TYPES):
        _complete_sync(user_id)
        return {"status": "completed", "types_completed": len(DATA_TYPES)}

    data_type = DATA_TYPES[type_index]

    # Calculate time range for this chunk
    # We go backwards from today: day 0 = today, day 1 = yesterday, etc.
    now = datetime.now(timezone.utc)
    end_time = now - timedelta(days=current_day)
    start_time = end_time - timedelta(hours=CHUNK_SIZE_HOURS)

    logger.info(
        f"Processing chunk: {data_type} day {current_day}/{TARGET_DAYS} "
        f"({start_time.date()} to {end_time.date()}) for user {user_id}"
    )

    # Update status to SYNCING
    redis_client.set(_get_sync_key(user_id, "status"), "SYNCING")

    # Fetch and save the chunk
    result = {"data_type": data_type, "day": current_day, "fetched": 0, "saved": 0}

    with SessionLocal() as db:
        try:
            from app.services.providers.garmin.summary import GarminSummaryService

            summary_service = GarminSummaryService()
            chunk_result = summary_service.fetch_and_save_single_chunk(
                db=db,
                user_id=user_uuid,
                data_type=data_type,
                start_time=start_time,
                end_time=end_time,
            )

            result["fetched"] = chunk_result.get("fetched", 0)
            result["saved"] = chunk_result.get("saved", 0)

            if chunk_result.get("error"):
                _add_error(user_id, data_type, current_day, chunk_result["error"])
                result["error"] = chunk_result["error"]

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error processing {data_type} day {current_day}: {e}")
            _add_error(user_id, data_type, current_day, error_msg)
            result["error"] = error_msg

            # Retry on transient errors
            if "rate limit" in error_msg.lower() or "timeout" in error_msg.lower():
                raise self.retry(exc=e, countdown=600)  # Retry in 10 minutes

    # Update last chunk timestamp
    redis_client.set(_get_sync_key(user_id, "last_chunk_at"), datetime.now(timezone.utc).isoformat())

    # Advance position
    next_day = current_day + 1
    if next_day >= TARGET_DAYS:
        # Move to next data type
        next_type_index = type_index + 1
        next_day = 0
        redis_client.set(_get_sync_key(user_id, "type_index"), str(next_type_index))

        if next_type_index >= len(DATA_TYPES):
            _complete_sync(user_id)
            result["status"] = "completed"
            return result

    redis_client.set(_get_sync_key(user_id, "current_day"), str(next_day))

    # Refresh TTL
    ttl = 7 * 24 * 3600
    for key_type in ["status", "type_index", "current_day", "started_at", "last_chunk_at", "errors"]:
        redis_client.expire(_get_sync_key(user_id, key_type), ttl)

    # Update status to WAITING before scheduling next chunk
    redis_client.set(_get_sync_key(user_id, "status"), "WAITING")

    # Schedule next chunk with appropriate delay
    delay = _get_chunk_delay(data_type)
    process_garmin_summary_chunk.apply_async(args=[user_id], countdown=delay)

    result["next_chunk_delay"] = delay
    result["status"] = "waiting"
    return result


@shared_task
def start_garmin_summary_sync(user_id: str, resume: bool = False) -> dict[str, Any]:
    """Entry point task to start Garmin summary sync.

    This task initializes the sync state and triggers the first chunk.

    Args:
        user_id: UUID string of the user
        resume: If True, resume from last position

    Returns:
        Dict with initial status
    """
    try:
        user_uuid = UUID(user_id)
    except ValueError as e:
        logger.error(f"Invalid user_id: {user_id}")
        return {"error": f"Invalid user_id: {e}"}

    # Verify user has Garmin connection
    with SessionLocal() as db:
        from app.repositories.user_connection_repository import UserConnectionRepository

        connection_repo = UserConnectionRepository()
        connection = connection_repo.get_by_user_and_provider(db, user_uuid, "garmin")

        if not connection:
            return {"error": "No Garmin connection found for user"}

    # Initialize sync state
    init_result = start_sync(user_id, resume=resume)
    if "error" in init_result:
        return init_result

    # Trigger first chunk immediately
    process_garmin_summary_chunk.delay(user_id)

    logger.info(f"Started Garmin summary sync for user {user_id} (resume={resume})")
    return {
        "status": "started",
        "resume": resume,
        "target_days": TARGET_DAYS,
        "total_types": len(DATA_TYPES),
        "data_types": DATA_TYPES,
    }
