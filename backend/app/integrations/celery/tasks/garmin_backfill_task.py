"""Celery task for chaining Garmin backfill requests.

This task manages the sequential fetching of historical Garmin data.
Each backfill request fetches ONE data type for ONE day, then waits
for webhook delivery before triggering the next request.

Flow: sleeps → webhook → dailies → webhook → ... → hrv → webhook → next day
"""

from datetime import datetime, timedelta, timezone
from logging import getLogger
from typing import Any
from uuid import UUID

from app.database import SessionLocal
from app.integrations.redis_client import get_redis_client
from app.repositories.user_connection_repository import UserConnectionRepository
from app.services.providers.factory import ProviderFactory
from app.services.providers.garmin.backfill import GarminBackfillService
from celery import shared_task

logger = getLogger(__name__)

# Redis key prefixes for backfill tracking
REDIS_PREFIX = "garmin:backfill"

# Data types to backfill in sequence
DATA_TYPES = ["sleeps", "dailies", "epochs", "bodyComps", "hrv"]


def _get_backfill_key(user_id: str | UUID, key_type: str) -> str:
    """Generate Redis key for backfill tracking."""
    return f"{REDIS_PREFIX}:{user_id}:{key_type}"


def get_backfill_status(user_id: str | UUID) -> dict[str, Any]:
    """Get current backfill status for a user.

    Returns:
        {
            "in_progress": bool,
            "days_completed": int,
            "current_data_type_index": int,
            "current_data_type": str,
            "current_end_date": str | None,
            "target_days": int
        }
    """
    redis_client = get_redis_client()
    in_progress = redis_client.get(_get_backfill_key(user_id, "in_progress"))
    days_completed = redis_client.get(_get_backfill_key(user_id, "days_completed"))
    data_type_index = redis_client.get(_get_backfill_key(user_id, "current_data_type_index"))
    current_end_date = redis_client.get(_get_backfill_key(user_id, "current_end_date"))

    index = int(data_type_index) if data_type_index else 0
    # Ensure index is within bounds
    if index >= len(DATA_TYPES):
        index = 0

    return {
        "in_progress": in_progress == "1",
        "days_completed": int(days_completed) if days_completed else 0,
        "current_data_type_index": index,
        "current_data_type": DATA_TYPES[index],
        "current_end_date": current_end_date,
        "target_days": GarminBackfillService.MAX_BACKFILL_DAYS,
    }


def start_backfill(user_id: str | UUID) -> None:
    """Initialize backfill tracking for a user."""
    redis_client = get_redis_client()
    now = datetime.now(timezone.utc)

    # Set backfill state
    redis_client.set(_get_backfill_key(user_id, "in_progress"), "1")
    redis_client.set(_get_backfill_key(user_id, "days_completed"), "0")
    redis_client.set(_get_backfill_key(user_id, "current_data_type_index"), "0")
    redis_client.set(_get_backfill_key(user_id, "current_end_date"), now.isoformat())

    # Set TTL of 24 hours to auto-cleanup stale backfills
    for key_type in ["in_progress", "days_completed", "current_data_type_index", "current_end_date"]:
        redis_client.expire(_get_backfill_key(user_id, key_type), 86400)

    logger.info(f"Started backfill tracking for user {user_id}")


def complete_backfill(user_id: str | UUID) -> None:
    """Mark backfill as complete and clean up Redis keys."""
    redis_client = get_redis_client()

    redis_client.delete(_get_backfill_key(user_id, "in_progress"))
    redis_client.delete(_get_backfill_key(user_id, "current_data_type_index"))
    redis_client.delete(_get_backfill_key(user_id, "current_end_date"))
    # Keep days_completed for reference (with shorter TTL)
    redis_client.expire(_get_backfill_key(user_id, "days_completed"), 3600)

    logger.info(f"Completed backfill for user {user_id}")


@shared_task
def trigger_next_backfill(user_id: str) -> dict[str, Any]:
    """Trigger the next single backfill request in sequence.

    Called after each webhook delivery to chain requests one at a time.
    This avoids rate limiting by spreading requests over time.

    Sequence:
    1. sleeps for day 1 → webhook → dailies for day 1 → ...
    2. After all 5 data types → move to day 2
    3. After 30 days → complete

    Args:
        user_id: UUID string of the user

    Returns:
        Dict with status and what was triggered
    """
    redis_client = get_redis_client()

    try:
        user_uuid = UUID(user_id)
    except ValueError as e:
        logger.error(f"[trigger_next_backfill] Invalid user_id: {user_id}")
        return {"error": f"Invalid user_id: {e}"}

    # Check current progress
    status = get_backfill_status(user_id)

    if not status["in_progress"]:
        logger.info(f"Backfill not in progress for user {user_id}, skipping")
        return {"status": "not_in_progress"}

    data_type_index = status["current_data_type_index"]
    days_completed = status["days_completed"]

    # Check if we need to move to next day
    if data_type_index >= len(DATA_TYPES):
        # All data types done for this day, move to next day
        data_type_index = 0
        days_completed += 1
        redis_client.set(_get_backfill_key(user_id, "days_completed"), str(days_completed))
        redis_client.set(_get_backfill_key(user_id, "current_data_type_index"), "0")

        # Update end date to go back 1 day
        current_end_str = status["current_end_date"]
        if current_end_str:
            current_end = datetime.fromisoformat(current_end_str.replace("Z", "+00:00"))
            new_end = current_end - timedelta(days=1)
            redis_client.set(_get_backfill_key(user_id, "current_end_date"), new_end.isoformat())

        logger.info(f"Moving to day {days_completed + 1} for user {user_id}")

    # Check if all days are complete
    if days_completed >= GarminBackfillService.MAX_BACKFILL_DAYS:
        logger.info(f"Backfill complete for user {user_id}: {days_completed} days")
        complete_backfill(user_id)
        return {"status": "complete", "days_completed": days_completed}

    # Get current data type to trigger
    data_type = DATA_TYPES[data_type_index]

    # Calculate date range for current day
    current_end_str = redis_client.get(_get_backfill_key(user_id, "current_end_date"))
    if current_end_str:
        end_time = datetime.fromisoformat(current_end_str.replace("Z", "+00:00"))
    else:
        end_time = datetime.now(timezone.utc)

    start_time = end_time - timedelta(days=1)

    logger.info(
        f"Triggering backfill: {data_type} (type {data_type_index + 1}/{len(DATA_TYPES)}) "
        f"for day {days_completed + 1}/{GarminBackfillService.MAX_BACKFILL_DAYS} "
        f"({start_time.date()} to {end_time.date()}) for user {user_id}"
    )

    # Trigger backfill for SINGLE data type
    with SessionLocal() as db:
        try:
            # Get Garmin connection
            connection_repo = UserConnectionRepository()
            connection = connection_repo.get_by_user_and_provider(db, user_uuid, "garmin")

            if not connection:
                logger.error(f"No Garmin connection for user {user_id}")
                complete_backfill(user_id)
                return {"error": "No Garmin connection"}

            # Get backfill service from factory
            factory = ProviderFactory()
            garmin_strategy = factory.get_provider("garmin")

            if not garmin_strategy.oauth:
                logger.error("Garmin OAuth not configured")
                complete_backfill(user_id)
                return {"error": "Garmin OAuth not configured"}

            backfill_service = GarminBackfillService(
                provider_name="garmin",
                api_base_url="https://apis.garmin.com",
                oauth=garmin_strategy.oauth,
            )

            # Trigger backfill for SINGLE data type only
            result = backfill_service.trigger_backfill(
                db=db,
                user_id=user_uuid,
                data_types=[data_type],  # Only ONE data type
                start_time=start_time,
                end_time=end_time,
            )

            # Increment data type index for next call
            redis_client.incr(_get_backfill_key(user_id, "current_data_type_index"))

            # Refresh TTL
            for key_type in ["in_progress", "days_completed", "current_data_type_index", "current_end_date"]:
                redis_client.expire(_get_backfill_key(user_id, key_type), 86400)

            return {
                "status": "triggered",
                "data_type": data_type,
                "data_type_index": data_type_index + 1,
                "day": days_completed + 1,
                "start_date": start_time.isoformat(),
                "end_date": end_time.isoformat(),
                "triggered": result.get("triggered", []),
                "failed": result.get("failed", {}),
            }

        except Exception as e:
            logger.error(f"Error in trigger_next_backfill for user {user_id}: {e}")
            return {"error": str(e)}


# Keep old function name for backwards compatibility (exported from __init__.py)
continue_garmin_backfill = trigger_next_backfill
