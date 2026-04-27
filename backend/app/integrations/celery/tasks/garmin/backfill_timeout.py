"""Garmin backfill timeout detection and chain-stop error classification.

Contains the ``check_triggered_timeout`` Celery task and private helpers
for classifying errors that should stop the entire backfill chain.
"""

from datetime import datetime, timezone
from logging import getLogger
from typing import Any

from celery import shared_task

from app.integrations.celery.tasks.garmin.backfill_task import trigger_next_pending_type
from app.integrations.redis_client import get_redis_client
from app.services.providers.garmin.backfill_config import (
    DELAY_BETWEEN_TYPES,
    TRIGGERED_TIMEOUT_SECONDS,
)
from app.services.providers.garmin.backfill_state import (
    _get_key,
    complete_backfill,
    get_current_window,
    get_trace_id,
    get_type_skip_count,
    is_cancelled,
    is_retry_phase,
    mark_type_failed,
    mark_type_timed_out,
    persist_window_results,
    record_timed_out_entry,
    update_window_cell,
)
from app.utils.structured_logging import log_structured

logger = getLogger(__name__)


def _classify_chain_stop_error(status_code: int | None, error_text: str) -> tuple[str, str] | None:
    """Return (error_msg, log_msg) if the error should stop the entire backfill chain.

    Returns None if the error is transient and the chain should continue.
    """
    error_lower = error_text.lower()
    is_before_min_start = status_code == 400 and "min start time" in error_lower

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
    from app.services.providers.garmin.backfill_state import get_pending_types

    pending = get_pending_types(user_id)
    for pending_type in pending:
        mark_type_failed(user_id, pending_type, error_msg)
    persist_window_results(user_id, current_window)
    complete_backfill(user_id)


@shared_task
def check_triggered_timeout(user_id: str, data_type: str) -> dict[str, Any]:
    """Check if a triggered type has timed out and mark it as timed_out.

    Scheduled by trigger_backfill_for_type with countdown=TRIGGERED_TIMEOUT_SECONDS.
    If the type is still "triggered" after the timeout, it means Garmin never sent
    a webhook (e.g., user has no data for this type).
    """
    user_id_str = str(user_id)
    trace_id = get_trace_id(user_id_str)
    type_trace_id = get_trace_id(user_id_str, data_type)

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

    status = get_redis_client().get(_get_key(user_id_str, "types", data_type, "status"))

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
            check_triggered_timeout.apply_async(args=[user_id_str, data_type], countdown=remaining)
            return {"status": "rescheduled", "remaining": remaining}

    mark_type_timed_out(user_id_str, data_type)

    if is_retry_phase(user_id_str):
        mark_type_failed(user_id_str, data_type, "Timed out during retry (escalated to failed)")
        retry_window_str = get_redis_client().get(_get_key(user_id_str, "retry_current_window"))
        if retry_window_str:
            update_window_cell(user_id_str, int(retry_window_str), data_type, "failed")
    else:
        record_timed_out_entry(user_id_str, data_type, get_current_window(user_id_str))

    trigger_next_pending_type.apply_async(args=[user_id_str], countdown=DELAY_BETWEEN_TYPES)

    skip_count = get_type_skip_count(user_id_str, data_type)
    return {
        "status": "timed_out",
        "data_type": data_type,
        "skip_count": skip_count,
        "action": "timed_out",
    }
