"""Celery task for triggering backfill for a specific Garmin data type.

Handles the actual API call to Garmin, error classification, rate-limiting,
and scheduling the timeout checker.
"""

from datetime import timedelta
from logging import getLogger
from typing import Any
from uuid import UUID

from celery import shared_task
from fastapi import HTTPException

from app.database import SessionLocal
from app.integrations.redis_client import get_redis_client
from app.models import User
from app.repositories.user_connection_repository import UserConnectionRepository
from app.repositories.user_repository import UserRepository
from app.services.providers.garmin.backfill_config import (
    ACTIVITY_API_TYPES,
    BACKFILL_DATA_TYPES,
    DELAY_AFTER_RATE_LIMIT,
    DELAY_BETWEEN_TYPES,
    TRIGGERED_TIMEOUT_SECONDS,
)
from app.services.providers.garmin.backfill_state import (
    _get_key,
    get_current_window,
    get_trace_id,
    get_window_date_range,
    get_window_date_range_for_index,
    is_retry_phase,
    mark_type_failed,
    mark_type_success,
    mark_type_triggered,
    set_type_trace_id,
)
from app.services.providers.garmin.handlers.backfill import GarminBackfillService
from app.services.providers.garmin.oauth import GarminOAuth
from app.utils.sentry_helpers import log_and_capture_error
from app.utils.structured_logging import log_structured

logger = getLogger(__name__)


@shared_task
def trigger_backfill_for_type(user_id: str, data_type: str) -> dict[str, Any]:
    """Trigger backfill for a specific data type."""
    from app.integrations.celery.tasks.garmin.backfill_task import trigger_next_pending_type
    from app.integrations.celery.tasks.garmin.backfill_timeout import (
        _classify_chain_stop_error,
        _finalize_chain_stop,
        check_triggered_timeout,
    )

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

    if is_retry_phase(user_id):
        retry_window_str = get_redis_client().get(_get_key(user_id, "retry_current_window"))
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
            connection_repo = UserConnectionRepository()
            connection = connection_repo.get_by_user_and_provider(db, user_uuid, "garmin")

            if not connection:
                error = "No Garmin connection"
                mark_type_failed(user_id, data_type, error)
                return {"error": error}

            garmin_oauth = GarminOAuth(
                user_repo=UserRepository(User),
                connection_repo=UserConnectionRepository(),
                provider_name="garmin",
                api_base_url="https://apis.garmin.com",
            )
            backfill_service = GarminBackfillService(
                provider_name="garmin",
                api_base_url="https://apis.garmin.com",
                oauth=garmin_oauth,
            )

            mark_type_triggered(user_id, data_type)

            result = backfill_service.trigger_backfill(
                db=db,
                user_id=user_uuid,
                data_types=[data_type],
                start_time=start_time,
                end_time=end_time,
                trace_id=trace_id,
            )

            if data_type in result.get("failed", {}):
                error = result["failed"][data_type]
                status_code = result.get("failed_status_codes", {}).get(data_type)

                # Retry "min start time" errors with a shorter date range before giving up
                if status_code == 400 and "min start time" in error.lower():
                    fallback_days = 14 if data_type in ACTIVITY_API_TYPES else 31
                    start_time_fallback = end_time - timedelta(days=fallback_days)
                    log_structured(
                        logger,
                        "info",
                        "Retrying with shorter range after min-start-time error",
                        provider="garmin",
                        trace_id=trace_id,
                        type_trace_id=type_trace_id,
                        data_type=data_type,
                        fallback_days=fallback_days,
                        user_id=user_id,
                    )
                    retry_result = backfill_service.trigger_backfill(
                        db=db,
                        user_id=user_uuid,
                        data_types=[data_type],
                        start_time=start_time_fallback,
                        end_time=end_time,
                        trace_id=trace_id,
                    )
                    # If retry also failed, use the retry result instead
                    if data_type in retry_result.get("failed", {}):
                        error = retry_result["failed"][data_type]
                        status_code = retry_result.get("failed_status_codes", {}).get(data_type)
                    else:
                        # Retry succeeded — skip the failure handling below
                        if data_type in retry_result.get("duplicate", []):
                            mark_type_success(user_id, data_type)
                            trigger_next_pending_type.apply_async(args=[user_id], countdown=DELAY_BETWEEN_TYPES)
                            return {"status": "duplicate_skipped", "data_type": data_type}
                        check_triggered_timeout.apply_async(
                            args=[user_id, data_type], countdown=TRIGGERED_TIMEOUT_SECONDS
                        )
                        return {
                            "status": "triggered",
                            "data_type": data_type,
                            "start_date": start_time_fallback.isoformat(),
                            "end_date": end_time.isoformat(),
                        }

                mark_type_failed(user_id, data_type, error)

                chain_stop = _classify_chain_stop_error(status_code, error)
                if chain_stop:
                    error_msg, log_msg = chain_stop
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
                    _finalize_chain_stop(user_id, current_window, error_msg)
                    return {"status": "failed", "error": error_msg}

                is_rate_limit = status_code == 429 or "rate limit" in error.lower()
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
                trigger_next_pending_type.apply_async(args=[user_id], countdown=delay)
                return {"status": "failed", "error": error}

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

            chain_stop = _classify_chain_stop_error(e.status_code, error)
            if chain_stop:
                error_msg, log_msg = chain_stop
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
                _finalize_chain_stop(user_id, current_window, error_msg)
                return {"status": "failed", "error": error_msg}

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
            trigger_next_pending_type.apply_async(args=[user_id], countdown=DELAY_BETWEEN_TYPES)
            return {"error": error}
