"""Garmin backfill Redis state management.

Pure Redis key operations for tracking per-user backfill progress.
No Celery, no HTTP, no database — consumed by both the Celery task
orchestrator (garmin_backfill_task) and the webhook handler.

This package is split into:
- core: key helper, trace IDs, lock, cancellation, completion, overall status
- type_tracking: per-type status (pending/triggered/success/failed/timed_out)
- window_state: multi-window backfill state, date ranges, matrix persistence
- retry_state: retry phase queue and lifecycle
"""

from app.services.providers.garmin.backfill_state.core import (
    _get_key,
    acquire_backfill_lock,
    clear_cancel_flag,
    complete_backfill,
    force_release_backfill_lock,
    get_backfill_status,
    get_trace_id,
    is_cancelled,
    release_backfill_lock,
    set_cancel_flag,
    set_trace_id,
    set_type_trace_id,
)
from app.services.providers.garmin.backfill_state.retry_state import (
    clear_retry_state,
    enter_retry_phase,
    get_next_retry_target,
    get_retry_targets,
    is_retry_phase,
    record_timed_out_entry,
    setup_retry_window,
)
from app.services.providers.garmin.backfill_state.type_tracking import (
    get_pending_types,
    get_timed_out_types,
    get_type_skip_count,
    mark_type_failed,
    mark_type_success,
    mark_type_timed_out,
    mark_type_triggered,
    reset_type_status,
)
from app.services.providers.garmin.backfill_state.window_state import (
    advance_window,
    get_anchor_timestamp,
    get_completed_window_count,
    get_current_window,
    get_total_windows,
    get_window_date_range,
    get_window_date_range_for_index,
    init_window_state,
    persist_window_results,
    update_window_cell,
)

__all__ = [
    # core
    "_get_key",
    "acquire_backfill_lock",
    "clear_cancel_flag",
    "complete_backfill",
    "force_release_backfill_lock",
    "get_backfill_status",
    "get_trace_id",
    "is_cancelled",
    "release_backfill_lock",
    "set_cancel_flag",
    "set_trace_id",
    "set_type_trace_id",
    # type_tracking
    "get_pending_types",
    "get_timed_out_types",
    "get_type_skip_count",
    "mark_type_failed",
    "mark_type_success",
    "mark_type_timed_out",
    "mark_type_triggered",
    "reset_type_status",
    # window_state
    "advance_window",
    "get_anchor_timestamp",
    "get_completed_window_count",
    "get_current_window",
    "get_total_windows",
    "get_window_date_range",
    "get_window_date_range_for_index",
    "init_window_state",
    "persist_window_results",
    "update_window_cell",
    # retry_state
    "clear_retry_state",
    "enter_retry_phase",
    "get_next_retry_target",
    "get_retry_targets",
    "is_retry_phase",
    "record_timed_out_entry",
    "setup_retry_window",
]
