"""Celery task for Garmin backfill requests with per-type status tracking.

This task manages the fetching of historical Garmin data using 30-day batch requests.
Each of the data types is tracked independently with status: pending|triggered|success|failed.

Flow:
1. start_full_backfill() - Initialize tracking for all backfill types, trigger first type
2. trigger_backfill_for_type() - Trigger backfill for a specific type
3. mark_type_success() - Called by webhook when data received
4. trigger_next_pending_type() - Chain to next pending type

Redis state management lives in app.services.providers.garmin.backfill_state.
"""

from datetime import datetime, timedelta, timezone
from logging import getLogger
from typing import Any
from uuid import UUID

from fastapi import HTTPException

from app.database import SessionLocal
from app.integrations.redis_client import get_redis_client
from app.models import User
from app.repositories.user_connection_repository import UserConnectionRepository
from app.repositories.user_repository import UserRepository
from app.services.providers.garmin.backfill_config import (
    ACTIVITY_API_TYPES,
    BACKFILL_DATA_TYPES,
    BACKFILL_WINDOW_COUNT,
    DELAY_AFTER_RATE_LIMIT,
    DELAY_BETWEEN_TYPES,
    MAX_BACKFILL_DAYS,
    REDIS_TTL,
    TRIGGERED_TIMEOUT_SECONDS,
)
from app.services.providers.garmin.backfill_state import (
    _get_key,
    acquire_backfill_lock,
    advance_window,
    clear_cancel_flag,
    clear_retry_state,
    complete_backfill,
    enter_retry_phase,
    get_current_window,
    get_next_retry_target,
    get_pending_types,
    get_retry_targets,
    get_total_windows,
    get_trace_id,
    get_type_skip_count,
    get_window_date_range,
    get_window_date_range_for_index,
    init_window_state,
    is_cancelled,
    is_retry_phase,
    mark_type_failed,
    mark_type_success,
    mark_type_timed_out,
    mark_type_triggered,
    persist_window_results,
    record_timed_out_entry,
    release_backfill_lock,
    reset_type_status,
    set_trace_id,
    set_type_trace_id,
    setup_retry_window,
    update_window_cell,
)
from app.services.providers.garmin.handlers.backfill import GarminBackfillService
from app.services.providers.garmin.oauth import GarminOAuth
from app.utils.sentry_helpers import log_and_capture_error
from app.utils.structured_logging import log_structured
from celery import shared_task

logger = getLogger(__name__)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _classify_chain_stop_error(status_code: int | None, error_text: str) -> tuple[str, str] | None:
    """Return (error_msg, log_msg) if the error should stop the entire backfill chain.

    Returns None if the error is transient and the chain should continue.
    """
    error_lower = error_text.lower()
    is_before_min_start = status_code == 400 and "min start time" in error_lower

    # "Endpoint not enabled" (400) is NOT a chain-stopper — it may only
    # affect a single data type while the rest succeed normally.
    if not (status_code in (401, 403, 412) or is_before_min_start):
        return None

    if status_code == 401:
        return (
            "Authorization expired or revoked. Please re-authorize Garmin.",
            "401: token invalid, stopping backfill for all types",
        )
    if status_code == 412:
        return (
            "HISTORICAL_DATA_EXPORT permission not granted. User must re-authorize.",
            "412: permission precondition failed, stopping backfill for all types",
        )
    if is_before_min_start:
        return (
            "Requested date range is before Garmin's minimum start time. No older data available.",
            "400: before min start time, stopping backfill chain",
        )
    # 403 fallback
    return (
        "Historical data access not granted. User must re-authorize.",
        "403: marking all remaining types as failed",
    )


def _finalize_chain_stop(user_id: str, current_window: int, error_msg: str) -> None:
    """Mark all pending types as failed and finalize the backfill."""
    pending = get_pending_types(user_id)
    for pending_type in pending:
        mark_type_failed(user_id, pending_type, error_msg)
    persist_window_results(user_id, current_window)
    complete_backfill(user_id)


# ---------------------------------------------------------------------------
# Celery tasks
# ---------------------------------------------------------------------------


@shared_task
def start_full_backfill(user_id: str) -> dict[str, Any]:
    """Initialize and start full 30-day backfill for all backfill data types.

    This is called after OAuth connection to auto-trigger historical sync.
    Triggers the first type and the rest will chain via webhooks.
    If existing state is detected (resume after cancel/crash), resumes from current window.

    Args:
        user_id: UUID string of the user

    Returns:
        Dict with initialization status
    """
    try:
        UUID(user_id)  # Validate UUID format
    except ValueError as e:
        log_structured(
            logger,
            "error",
            "Invalid user_id",
            user_id=user_id,
            error=str(e),
        )
        return {"error": f"Invalid user_id: {e}"}

    # Skip backfill if user didn't grant HISTORICAL_DATA_EXPORT permission
    with SessionLocal() as db:
        connection_repo = UserConnectionRepository()
        connection = connection_repo.get_by_user_and_provider(db, UUID(user_id), "garmin")
        if not connection or not connection.scope or "HISTORICAL_DATA_EXPORT" not in connection.scope.split():
            log_structured(
                logger,
                "info",
                "Skipping backfill -- HISTORICAL_DATA_EXPORT not granted",
                provider="garmin",
                user_id=user_id,
                scope=connection.scope if connection else None,
            )
            return {"status": "skipped", "reason": "HISTORICAL_DATA_EXPORT permission not granted"}

    # Reject re-trigger if permanently failed
    if get_redis_client().get(_get_key(user_id, "permanently_failed")) == "1":
        log_structured(
            logger,
            "warning",
            "Backfill permanently failed -- cannot re-trigger",
            provider="garmin",
            user_id=user_id,
        )
        return {
            "error": "Backfill permanently failed after maximum attempts. Disconnect and reconnect to reset.",
            "status": "permanently_failed",
        }

    # Acquire exclusive lock -- reject if already in progress
    if not acquire_backfill_lock(user_id):
        log_structured(
            logger,
            "warning",
            "Backfill already in progress",
            provider="garmin",
            user_id=user_id,
        )
        return {"error": "Backfill already in progress", "status": "rejected"}

    # Generate trace ID for this backfill session
    trace_id = set_trace_id(user_id)

    # Check for existing state (resume detection)
    current_window = get_current_window(user_id)
    cancel_flag = is_cancelled(user_id)

    if current_window > 0 or cancel_flag:
        # Resume from persisted state
        clear_cancel_flag(user_id)
        pending = get_pending_types(user_id)

        log_structured(
            logger,
            "info",
            "Resuming backfill from persisted state",
            provider="garmin",
            trace_id=trace_id,
            user_id=user_id,
            window=current_window,
            pending_types=pending,
        )

        if pending:
            trigger_backfill_for_type.apply_async(args=[user_id, pending[0]], countdown=1)
        else:
            trigger_next_pending_type.apply_async(args=[user_id], countdown=1)

        return {
            "status": "resumed",
            "user_id": user_id,
            "trace_id": trace_id,
            "window": current_window,
        }

    # Fresh start -- initialize window state and reset types
    init_window_state(user_id, total_windows=BACKFILL_WINDOW_COUNT)

    log_structured(
        logger,
        "info",
        "Starting full backfill",
        provider="garmin",
        trace_id=trace_id,
        user_id=user_id,
        total_types=len(BACKFILL_DATA_TYPES),
        total_windows=BACKFILL_WINDOW_COUNT,
        target_days=MAX_BACKFILL_DAYS,
    )

    for data_type in BACKFILL_DATA_TYPES:
        reset_type_status(user_id, data_type)

    first_type = BACKFILL_DATA_TYPES[0]
    trigger_backfill_for_type.apply_async(args=[user_id, first_type], countdown=1)

    return {
        "status": "started",
        "user_id": user_id,
        "trace_id": trace_id,
        "total_types": len(BACKFILL_DATA_TYPES),
        "total_windows": BACKFILL_WINDOW_COUNT,
        "target_days": MAX_BACKFILL_DAYS,
        "first_type": first_type,
    }


@shared_task
def check_triggered_timeout(user_id: str, data_type: str) -> dict[str, Any]:
    """Check if a triggered type has timed out and mark it as timed_out.

    Scheduled by trigger_backfill_for_type with countdown=TRIGGERED_TIMEOUT_SECONDS.
    If the type is still "triggered" after the timeout, it means Garmin never sent
    a webhook (e.g., user has no data for this type).

    Args:
        user_id: UUID string of the user
        data_type: The data type to check

    Returns:
        Dict with timeout check result
    """
    user_id_str = str(user_id)
    trace_id = get_trace_id(user_id_str)
    type_trace_id = get_trace_id(user_id_str, data_type)

    # 0. Check cancel flag -- persist state and stop if cancelled
    if is_cancelled(user_id_str):
        current_window = get_current_window(user_id_str)
        persist_window_results(user_id_str, current_window)
        log_structured(
            logger,
            "info",
            "Timeout check: backfill cancelled, stopping",
            provider="garmin",
            trace_id=trace_id,
            type_trace_id=type_trace_id,
            data_type=data_type,
            user_id=user_id_str,
        )
        return {"status": "cancelled"}

    # 1. Read current status
    status = get_redis_client().get(_get_key(user_id_str, "types", data_type, "status"))

    # 2. If not "triggered" → already resolved by webhook
    if status != "triggered":
        log_structured(
            logger,
            "info",
            "Timeout check: type already resolved",
            provider="garmin",
            trace_id=trace_id,
            type_trace_id=type_trace_id,
            data_type=data_type,
            current_status=status,
            user_id=user_id_str,
        )
        return {"status": "already_resolved", "current_status": status}

    # 3. Verify triggered_at is actually older than TRIGGERED_TIMEOUT_SECONDS
    triggered_at_str = get_redis_client().get(_get_key(user_id_str, "types", data_type, "triggered_at"))
    if triggered_at_str:
        triggered_at = datetime.fromisoformat(triggered_at_str)
        elapsed = (datetime.now(timezone.utc) - triggered_at).total_seconds()
        if elapsed < TRIGGERED_TIMEOUT_SECONDS:
            remaining = int(TRIGGERED_TIMEOUT_SECONDS - elapsed) + 1
            log_structured(
                logger,
                "info",
                "Timeout check: not yet expired, rescheduling",
                provider="garmin",
                trace_id=trace_id,
                type_trace_id=type_trace_id,
                data_type=data_type,
                elapsed=int(elapsed),
                remaining=remaining,
                user_id=user_id_str,
            )
            check_triggered_timeout.apply_async(args=[user_id, data_type], countdown=remaining)
            return {"status": "rescheduled", "remaining": remaining}

    # 4. Mark as timed_out
    mark_type_timed_out(user_id_str, data_type)

    # During retry phase, a second timeout escalates to failed
    if is_retry_phase(user_id_str):
        mark_type_failed(user_id_str, data_type, "Timed out during retry (escalated to failed)")
        retry_window_str = get_redis_client().get(_get_key(user_id_str, "retry_current_window"))
        if retry_window_str:
            update_window_cell(user_id_str, int(retry_window_str), data_type, "failed")
    else:
        # Only record timed-out entry during initial run (not retry phase)
        record_timed_out_entry(user_id, data_type, get_current_window(user_id))

    # 5. Chain to next type
    trigger_next_pending_type.apply_async(args=[user_id], countdown=DELAY_BETWEEN_TYPES)

    skip_count = get_type_skip_count(user_id_str, data_type)
    return {
        "status": "timed_out",
        "data_type": data_type,
        "skip_count": skip_count,
        "action": "timed_out",
    }


@shared_task
def trigger_backfill_for_type(user_id: str, data_type: str) -> dict[str, Any]:
    """Trigger backfill for a specific data type.

    Args:
        user_id: UUID string of the user
        data_type: One of the backfill data types

    Returns:
        Dict with trigger status
    """
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

    # During retry phase, use the retry window's date range (not current sequential window)
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
                    fallback_days = 14 if data_type in ACTIVITY_API_TYPES else 31
                    start_time_fallback = end_time - timedelta(days=fallback_days)
                    log_structured(
                        logger,
                        "info",
                        "Retrying with shorter range",
                        provider="garmin",
                        trace_id=trace_id,
                        type_trace_id=type_trace_id,
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

            if data_type in result.get("failed", {}):
                error = result["failed"][data_type]
                status_code = result.get("failed_status_codes", {}).get(data_type)
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

            # 409 duplicate — Garmin already processed this timeframe
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

    if is_cancelled(user_id):
        current_window = get_current_window(user_id)
        persist_window_results(user_id, current_window)
        log_structured(
            logger,
            "info",
            "Backfill cancelled",
            provider="garmin",
            trace_id=trace_id,
            user_id=user_id,
        )
        return {"status": "cancelled"}

    pending_types = get_pending_types(user_id)

    if not pending_types:
        if is_retry_phase(user_id):
            retry_window_str = get_redis_client().get(_get_key(user_id, "retry_current_window"))
            retry_type_str = get_redis_client().get(_get_key(user_id, "retry_current_type"))
            if retry_window_str and retry_type_str:
                current_status = get_redis_client().get(_get_key(user_id, "types", retry_type_str, "status"))
                if current_status == "success":
                    update_window_cell(user_id, int(retry_window_str), retry_type_str, "done")
                elif current_status == "timed_out":
                    update_window_cell(user_id, int(retry_window_str), retry_type_str, "failed")
                    mark_type_failed(user_id, retry_type_str, "Timed out during retry (escalated to failed)")
                elif current_status == "failed":
                    update_window_cell(user_id, int(retry_window_str), retry_type_str, "failed")

            next_entry = get_next_retry_target(user_id)
            if next_entry:
                setup_retry_window(user_id, next_entry["window"])
                get_redis_client().setex(_get_key(user_id, "retry_current_type"), REDIS_TTL, next_entry["type"])
                reset_type_status(user_id, next_entry["type"])
                trigger_backfill_for_type.apply_async(
                    args=[user_id, next_entry["type"]],
                    countdown=DELAY_BETWEEN_TYPES,
                )
                log_structured(
                    logger,
                    "info",
                    "Retry phase: triggering next type",
                    provider="garmin",
                    trace_id=trace_id,
                    user_id=user_id,
                    retry_type=next_entry["type"],
                    retry_window=next_entry["window"],
                )
                return {"status": "retry_phase", "retrying": next_entry}

            clear_retry_state(user_id)
            release_backfill_lock(user_id)
            complete_backfill(user_id)
            log_structured(
                logger,
                "info",
                "Retry phase complete, backfill finalized",
                provider="garmin",
                trace_id=trace_id,
                user_id=user_id,
            )
            return {"status": "complete"}

        has_more = advance_window(user_id)
        if has_more:
            current_window = get_current_window(user_id)
            log_structured(
                logger,
                "info",
                "Window complete, advancing to next",
                provider="garmin",
                trace_id=trace_id,
                user_id=user_id,
                window=current_window,
                total_windows=get_total_windows(user_id),
            )
            first_type = BACKFILL_DATA_TYPES[0]
            trigger_backfill_for_type.apply_async(args=[user_id, first_type], countdown=DELAY_BETWEEN_TYPES)
            return {"status": "advancing_window", "window": current_window}

        retry_entries = get_retry_targets(user_id)
        if retry_entries and not is_retry_phase(user_id):
            enter_retry_phase(user_id, retry_entries)
            first_entry = get_next_retry_target(user_id)
            if first_entry:
                setup_retry_window(user_id, first_entry["window"])
                get_redis_client().setex(
                    _get_key(user_id, "retry_current_type"),
                    REDIS_TTL,
                    first_entry["type"],
                )
                reset_type_status(user_id, first_entry["type"])
                trigger_backfill_for_type.apply_async(
                    args=[user_id, first_entry["type"]],
                    countdown=DELAY_BETWEEN_TYPES,
                )
                log_structured(
                    logger,
                    "info",
                    "Retry phase: triggering first type",
                    provider="garmin",
                    trace_id=trace_id,
                    user_id=user_id,
                    retry_type=first_entry["type"],
                    retry_window=first_entry["window"],
                )
                return {"status": "retry_phase", "retrying": first_entry}

        clear_retry_state(user_id)
        release_backfill_lock(user_id)
        complete_backfill(user_id)
        completed_windows = get_current_window(user_id)
        log_structured(
            logger,
            "info",
            "Backfill complete",
            provider="garmin",
            trace_id=trace_id,
            user_id=user_id,
            completed_windows=completed_windows,
        )
        return {"status": "complete", "completed_windows": completed_windows}

    next_type = pending_types[0]
    log_structured(
        logger,
        "info",
        "Triggering next backfill type",
        provider="garmin",
        trace_id=trace_id,
        user_id=user_id,
        next_type=next_type,
        remaining=len(pending_types),
    )

    trigger_backfill_for_type.apply_async(args=[user_id, next_type], countdown=DELAY_BETWEEN_TYPES)

    return {"status": "continuing", "next_type": next_type, "pending_count": len(pending_types)}


# Aliases for backwards compatibility
trigger_next_backfill = trigger_next_pending_type
continue_garmin_backfill = trigger_next_pending_type
