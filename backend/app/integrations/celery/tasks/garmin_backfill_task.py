"""Celery tasks for Garmin backfill orchestration.

Contains the entry-point task (``start_full_backfill``) and the chaining task
(``trigger_next_pending_type``) that advances through data types and windows.

Per-type trigger logic lives in ``garmin_backfill_trigger``.
Timeout detection lives in ``garmin_backfill_timeout``.
Redis state management lives in ``app.services.providers.garmin.backfill_state``.
"""

from logging import getLogger
from typing import Any
from uuid import UUID

from celery import shared_task

from app.database import SessionLocal
from app.integrations.celery.tasks.garmin_backfill_trigger import trigger_backfill_for_type
from app.integrations.redis_client import get_redis_client
from app.repositories.user_connection_repository import UserConnectionRepository
from app.services.providers.garmin.backfill_config import (
    BACKFILL_DATA_TYPES,
    BACKFILL_WINDOW_COUNT,
    DELAY_BETWEEN_TYPES,
    MAX_BACKFILL_DAYS,
    REDIS_TTL,
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
    init_window_state,
    is_cancelled,
    is_retry_phase,
    mark_type_failed,
    persist_window_results,
    reset_type_status,
    set_trace_id,
    setup_retry_window,
    update_window_cell,
)
from app.utils.structured_logging import log_structured

logger = getLogger(__name__)


@shared_task
def start_full_backfill(user_id: str) -> dict[str, Any]:
    """Initialize and start full 30-day backfill for all backfill data types.

    This is called after OAuth connection to auto-trigger historical sync.
    Triggers the first type and the rest will chain via webhooks.
    If existing state is detected (resume after cancel/crash), resumes from current window.
    """

    try:
        UUID(user_id)
    except ValueError as e:
        log_structured(
            logger,
            "error",
            "Invalid user_id",
            user_id=user_id,
            error=str(e),
        )
        return {"error": f"Invalid user_id: {e}"}

    # Skip backfill only when we *know* the user hasn't granted HISTORICAL_DATA_EXPORT.
    # scope=None means the permissions fetch failed during OAuth (best-effort) and the
    # userPermissionsChange webhook hasn't updated it yet — treat that as unknown and
    # proceed so the user doesn't get silently blocked.
    with SessionLocal() as db:
        connection_repo = UserConnectionRepository()
        connection = connection_repo.get_by_user_and_provider(db, UUID(user_id), "garmin")
        if not connection:
            log_structured(
                logger,
                "info",
                "Skipping backfill -- no Garmin connection found",
                provider="garmin",
                user_id=user_id,
            )
            return {"status": "skipped", "reason": "No Garmin connection found"}
        if connection.scope is not None and "HISTORICAL_DATA_EXPORT" not in connection.scope.split():
            log_structured(
                logger,
                "info",
                "Skipping backfill -- HISTORICAL_DATA_EXPORT not granted",
                provider="garmin",
                user_id=user_id,
                scope=connection.scope,
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

    # Acquire exclusive lock
    if not acquire_backfill_lock(user_id):
        log_structured(
            logger,
            "warning",
            "Backfill already in progress",
            provider="garmin",
            user_id=user_id,
        )
        return {"error": "Backfill already in progress", "status": "rejected"}

    trace_id = set_trace_id(user_id)

    # Check for existing state (resume detection)
    current_window = get_current_window(user_id)
    cancel_flag = is_cancelled(user_id)

    if current_window > 0 or cancel_flag:
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

    # Fresh start
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
def trigger_next_pending_type(user_id: str) -> dict[str, Any]:
    """Trigger the next pending data type in the backfill sequence.

    Called after a webhook receives data for a type, or after a type fails.
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
