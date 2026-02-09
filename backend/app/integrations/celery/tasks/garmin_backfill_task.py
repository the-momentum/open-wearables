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
from app.services.providers.garmin.handlers.backfill import GarminBackfillService
from app.utils.structured_logging import log_structured
from celery import shared_task

logger = getLogger(__name__)

# Redis key prefixes for backfill tracking
REDIS_PREFIX = "garmin:backfill"
REDIS_TTL = 86400 * 7  # 7 days TTL for backfill tracking

# Garmin rate limit: 100 requests per 60 seconds
GARMIN_RATE_LIMIT_WINDOW = 60  # seconds
GARMIN_RATE_LIMIT_REQUESTS = 100
GARMIN_BACKFILL_BUDGET_PCT = 0.3  # Reserve 30% of rate limit for backfill

# Rate limiting delays (derived from Garmin's 100 req/min limit)
_backfill_budget = int(GARMIN_RATE_LIMIT_REQUESTS * GARMIN_BACKFILL_BUDGET_PCT)  # 30 req/min
DELAY_BETWEEN_TYPES = GARMIN_RATE_LIMIT_WINDOW // _backfill_budget  # 2s between types
DELAY_AFTER_RATE_LIMIT = GARMIN_RATE_LIMIT_WINDOW  # Wait for full window reset (60s)

# All 16 data types to backfill
ALL_DATA_TYPES = [
    "sleeps",
    "dailies",
    "epochs",
    "bodyComps",
    "hrv",
    "activities",
    "activityDetails",
    "moveiq",
    "healthSnapshot",
    "stressDetails",
    "respiration",
    "pulseOx",
    "bloodPressures",
    "userMetrics",
    "skinTemp",
    "mct",
]


def _get_key(user_id: str | UUID, *parts: str) -> str:
    """Generate Redis key for backfill tracking."""
    return ":".join([REDIS_PREFIX, str(user_id), *parts])


def set_trace_id(user_id: str | UUID) -> str:
    """Generate and store a trace ID for a user's backfill session."""
    redis_client = get_redis_client()
    trace_id = str(uuid4())[:8]  # Short trace ID for readability
    redis_client.setex(_get_key(user_id, "trace_id"), REDIS_TTL, trace_id)
    return trace_id


def get_trace_id(user_id: str | UUID) -> str | None:
    """Get the active backfill trace ID for a user, if any."""
    redis_client = get_redis_client()
    return redis_client.get(_get_key(user_id, "trace_id"))


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

    for data_type in ALL_DATA_TYPES:
        type_status = redis_client.get(_get_key(user_id_str, "types", data_type, "status"))
        status = type_status if type_status else "pending"

        type_info: dict[str, Any] = {"status": status}

        if status == "triggered":
            triggered_at = redis_client.get(_get_key(user_id_str, "types", data_type, "triggered_at"))
            if triggered_at:
                type_info["triggered_at"] = triggered_at
            triggered_count += 1
        elif status == "success":
            completed_at = redis_client.get(_get_key(user_id_str, "types", data_type, "completed_at"))
            if completed_at:
                type_info["completed_at"] = completed_at
            success_count += 1
        elif status == "failed":
            error = redis_client.get(_get_key(user_id_str, "types", data_type, "error"))
            if error:
                type_info["error"] = error
            failed_count += 1
        else:
            pending_count += 1

        types_status[data_type] = type_info

    # Determine overall status
    if success_count == len(ALL_DATA_TYPES):
        overall_status = "complete"
    elif success_count > 0 and failed_count > 0 and pending_count == 0 and triggered_count == 0:
        overall_status = "partial"
    elif triggered_count > 0 or (success_count > 0 and pending_count > 0):
        overall_status = "in_progress"
    else:
        overall_status = "pending"

    return {
        "overall_status": overall_status,
        "types": types_status,
        "success_count": success_count,
        "failed_count": failed_count,
        "pending_count": pending_count,
        "triggered_count": triggered_count,
        "total_types": len(ALL_DATA_TYPES),
        # Legacy compatibility
        "in_progress": overall_status == "in_progress",
        "days_completed": GarminBackfillService.MAX_BACKFILL_DAYS if overall_status == "complete" else 0,
        "target_days": GarminBackfillService.MAX_BACKFILL_DAYS,
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
    log_structured(
        logger, "info", "Marked type as triggered", trace_id=trace_id, data_type=data_type, user_id=user_id_str
    )


def mark_type_success(user_id: str | UUID, data_type: str) -> None:
    """Mark a data type as successfully completed (webhook received data)."""
    redis_client = get_redis_client()
    user_id_str = str(user_id)
    now = datetime.now(timezone.utc).isoformat()

    redis_client.setex(_get_key(user_id_str, "types", data_type, "status"), REDIS_TTL, "success")
    redis_client.setex(_get_key(user_id_str, "types", data_type, "completed_at"), REDIS_TTL, now)

    trace_id = get_trace_id(user_id_str)
    log_structured(
        logger, "info", "Marked type as success", trace_id=trace_id, data_type=data_type, user_id=user_id_str
    )


def mark_type_failed(user_id: str | UUID, data_type: str, error: str) -> None:
    """Mark a data type as failed."""
    redis_client = get_redis_client()
    user_id_str = str(user_id)

    redis_client.setex(_get_key(user_id_str, "types", data_type, "status"), REDIS_TTL, "failed")
    redis_client.setex(_get_key(user_id_str, "types", data_type, "error"), REDIS_TTL, error)

    trace_id = get_trace_id(user_id_str)
    log_structured(
        logger,
        "error",
        "Marked type as failed",
        trace_id=trace_id,
        data_type=data_type,
        error=error,
        user_id=user_id_str,
    )


def reset_type_status(user_id: str | UUID, data_type: str) -> None:
    """Reset a data type to pending status (for retry)."""
    redis_client = get_redis_client()
    user_id_str = str(user_id)

    # Delete all keys for this type
    for key_suffix in ["status", "triggered_at", "completed_at", "error"]:
        redis_client.delete(_get_key(user_id_str, "types", data_type, key_suffix))

    logger.info(f"Reset {data_type} status for user {user_id_str}")


def complete_backfill(user_id: str | UUID) -> None:
    """Mark entire backfill as complete (all types processed)."""
    redis_client = get_redis_client()
    user_id_str = str(user_id)

    # Set overall complete marker with shorter TTL (1 day)
    redis_client.setex(_get_key(user_id_str, "overall_complete"), 86400, "1")

    trace_id = get_trace_id(user_id_str)
    log_structured(logger, "info", "Completed full backfill", trace_id=trace_id, user_id=user_id_str)


@shared_task
def start_full_backfill(user_id: str) -> dict[str, Any]:
    """Initialize and start full 30-day backfill for all 16 data types.

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
        logger.error(f"Invalid user_id: {user_id}")
        return {"error": f"Invalid user_id: {e}"}

    # Generate trace ID for this backfill session
    trace_id = set_trace_id(user_id)

    log_structured(
        logger,
        "info",
        "Starting full backfill",
        trace_id=trace_id,
        user_id=user_id,
        total_types=len(ALL_DATA_TYPES),
        max_days=GarminBackfillService.MAX_BACKFILL_DAYS,
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
        "first_type": first_type,
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
        logger.error(f"Invalid user_id: {user_id}")
        return {"error": f"Invalid user_id: {e}"}

    trace_id = get_trace_id(user_id)

    # Calculate date range: 30 days max for all data types
    # No summary gap since REST endpoints are removed - backfill from now
    max_days = GarminBackfillService.get_max_days_for_type(data_type)
    now = datetime.now(timezone.utc)
    end_time = now
    start_time = now - timedelta(days=max_days)  # Start at 30 days ago

    log_structured(
        logger,
        "info",
        "Triggering backfill for type",
        trace_id=trace_id,
        data_type=data_type,
        max_days=max_days,
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
                    fallback_days = 14 if data_type in GarminBackfillService.ACTIVITY_API_TYPES else 31
                    start_time_fallback = end_time - timedelta(days=fallback_days)
                    log_structured(
                        logger,
                        "info",
                        "Retrying with shorter range",
                        trace_id=trace_id,
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
                        trace_id=trace_id,
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
                        trace_id=trace_id,
                        data_type=data_type,
                        delay_seconds=delay,
                        user_id=user_id,
                    )
                # Still trigger next type even if this one failed (with delay)
                trigger_next_pending_type.apply_async(args=[user_id], countdown=delay)
                return {"status": "failed", "error": error}

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
                trace_id=trace_id,
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
                    trace_id=trace_id,
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
                    trace_id=trace_id,
                    data_type=data_type,
                    delay_seconds=delay,
                    user_id=user_id,
                )
            # Try to continue with next type (with delay)
            trigger_next_pending_type.apply_async(args=[user_id], countdown=delay)
            return {"status": "failed", "error": error}

        except Exception as e:
            error = str(e)
            log_structured(
                logger,
                "error",
                "Error triggering backfill",
                trace_id=trace_id,
                data_type=data_type,
                error=error,
                user_id=user_id,
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
        status = get_backfill_status(user_id)
        if status["failed_count"] == 0:
            complete_backfill(user_id)
            log_structured(
                logger,
                "info",
                "Backfill complete",
                trace_id=trace_id,
                user_id=user_id,
                success_count=status["success_count"],
            )
            return {"status": "complete", "success_count": status["success_count"]}
        log_structured(
            logger,
            "info",
            "Backfill finished with failures",
            trace_id=trace_id,
            user_id=user_id,
            success_count=status["success_count"],
            failed_count=status["failed_count"],
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
