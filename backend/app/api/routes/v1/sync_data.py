import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Query, status

from app.database import DbSession
from app.integrations.celery.tasks import (
    GARMIN_BACKFILL_DATA_TYPES,
    get_garmin_backfill_status,
    reset_garmin_type_status,
    set_garmin_cancel_flag,
    sync_vendor_data,
    trigger_garmin_backfill_for_type,
)
from app.schemas.enums import ProviderName
from app.services import ApiKeyDep
from app.services.providers.factory import ProviderFactory
from app.utils.exceptions import UnsupportedProviderError

logger = logging.getLogger(__name__)

router = APIRouter()
factory = ProviderFactory()
DEFAULT_HISTORICAL_DAYS = 90


def _queue_pull_sync(
    user_id: UUID,
    provider_value: str,
    start_date: str | None,
    end_date: str | None,
    *,
    is_historical: bool = False,
) -> Any:
    """Enqueue a pull-API sync task and return the Celery AsyncResult."""
    return sync_vendor_data.delay(
        user_id=str(user_id),
        start_date=start_date,
        end_date=end_date,
        providers=[provider_value],
        is_historical=is_historical,
    )


class SyncDataType(str, Enum):
    """Types of data to sync from provider."""

    WORKOUTS = "workouts"
    DATA_247 = "247"  # Sleep, recovery, activity samples
    ALL = "all"


@router.post("/{provider}/users/{user_id}/sync")
def sync_user_data(
    provider: Annotated[ProviderName, Path(description="Data provider")],
    user_id: UUID,
    db: DbSession,
    _api_key: ApiKeyDep,
    # Data type selection
    data_type: Annotated[
        SyncDataType,
        Query(description="Type of data to sync: workouts, 247 (sleep/recovery/activity), or all"),
    ] = SyncDataType.ALL,
    # Suunto-specific parameters
    since: Annotated[
        int,
        Query(description="Unix timestamp to synchronize data since (0 = all, Suunto only)"),
    ] = 0,
    limit: Annotated[
        int,
        Query(description="Maximum number of items (Suunto: max 100)", le=100),
    ] = 50,
    offset: Annotated[int, Query(description="Offset for pagination (Suunto only)")] = 0,
    filter_by_modification_time: Annotated[
        bool,
        Query(description="Filter by modification time instead of creation time (Suunto only)"),
    ] = True,
    # Polar-specific parameters
    samples: Annotated[bool, Query(description="Synchronize sample data (Polar only)")] = False,
    zones: Annotated[bool, Query(description="Synchronize zones data (Polar only)")] = False,
    route: Annotated[bool, Query(description="Synchronize route data (Polar only)")] = False,
    # Garmin-specific parameters (backfill API - no pull token required)
    summary_start_time: Annotated[
        str | None,
        Query(description="Activity start time as Unix timestamp or ISO 8601 date (Garmin only)"),
    ] = None,
    summary_end_time: Annotated[
        str | None,
        Query(description="Activity end time as Unix timestamp or ISO 8601 date (Garmin only)"),
    ] = None,
    # Async mode - dispatch to Celery worker instead of blocking
    run_async: Annotated[
        bool,
        Query(
            alias="async",
            description="Run sync asynchronously via Celery (default: true). Set false for sync.",
        ),
    ] = True,
) -> dict[str, bool | dict | str]:
    """
    Synchronize data from fitness provider API for a specific user.

    **Data Types:**
    - `workouts`: Workouts/exercises/activities
    - `247`: 24/7 data including sleep, recovery, and activity samples
    - `all`: All available data types

    **Provider-specific:**
    - **Suunto**: Supports workouts and 247 data with pagination
    - **Polar**: Supports workouts (exercises) only
    - **Garmin**: Data arrives via webhooks (backfill for 30-day history)
    - **Whoop**: Supports workouts and 247 data (sleep/recovery)

    **Execution Mode:**
    - `async=true` (default): Dispatches sync to background Celery worker. Returns immediately with task ID.
    - `async=false`: Executes synchronously (may timeout for large data sets).

    Requires valid API key and active connection for the user.
    """
    if run_async:
        # The async worker (sync_vendor_data) always syncs all data types and
        # does not accept per-type or provider-specific flags. Reject requests
        # that would silently be ignored by the task.
        non_default_params = {
            "data_type": data_type != SyncDataType.ALL,
            "since": since != 0,
            "limit": limit != 50,
            "offset": offset != 0,
            "filter_by_modification_time": not filter_by_modification_time,
            "samples": samples,
            "zones": zones,
            "route": route,
        }
        unsupported = [k for k, v in non_default_params.items() if v]
        if unsupported:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Parameters {unsupported} are not supported in async mode. "
                    "Use async=false or omit provider-specific parameters."
                ),
            )

        start_date_iso: str | None = None
        if since > 0:
            start_date_iso = datetime.fromtimestamp(since).isoformat()
        elif summary_start_time:
            start_date_iso = summary_start_time

        task = _queue_pull_sync(user_id, provider.value, start_date_iso, summary_end_time)
        return {
            "success": True,
            "async": True,
            "task_id": task.id,
            "message": f"Sync task queued for {provider.value}. Check task status for results.",
        }

    # Synchronous mode
    strategy = factory.get_provider(provider.value)

    results: dict[str, Any] = {}

    # Collect all parameters
    params = {
        "since": since,
        "limit": limit,
        "offset": offset,
        "filter_by_modification_time": filter_by_modification_time,
        "samples": samples,
        "zones": zones,
        "route": route,
        "summary_start_time": summary_start_time,
        "summary_end_time": summary_end_time,
    }

    # Sync workouts if requested
    if data_type in (SyncDataType.WORKOUTS, SyncDataType.ALL):
        if strategy.workouts:
            results["workouts"] = strategy.workouts.load_data(db, user_id, **params)
        elif data_type == SyncDataType.WORKOUTS:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail=f"Provider '{provider.value}' does not support workouts",
            )

    if data_type in (SyncDataType.DATA_247, SyncDataType.ALL):
        if strategy.data_247:
            load_fn = getattr(strategy.data_247, "load_and_save_all", None) or getattr(
                strategy.data_247, "load_all_247_data", None
            )
            if load_fn is None:
                results["data_247"] = None
            else:
                start_dt = datetime.fromtimestamp(since) if since else datetime.now() - timedelta(days=30)
                end_dt = datetime.now()
                results["data_247"] = load_fn(db, user_id, start_time=start_dt, end_time=end_dt)
        elif data_type == SyncDataType.DATA_247:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail=f"Provider '{provider.value}' does not support 247 data (sleep/recovery/activity)",
            )

    if not results:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Provider '{provider.value}' does not support any requested data types",
        )

    return {"success": all(results.values()), "details": results}


# =============================================================================
# Garmin Backfill Endpoints (webhook-based, 30-day sync)
# =============================================================================


@router.get("/garmin/users/{user_id}/backfill/status")
def get_garmin_backfill_status_endpoint(
    user_id: UUID,
    _api_key: ApiKeyDep,
) -> dict[str, Any]:
    """
    Get Garmin backfill status for backfill data types.

    The backfill is webhook-based and auto-triggered after OAuth connection.
    Returns status for each data type independently. Max 30 days of history.

    **Response Fields:**
    - `overall_status`: pending | in_progress | complete | cancelled | retry_in_progress | permanently_failed
    - `current_window`: Current window index (0-based)
    - `total_windows`: Total number of 30-day windows (12)
    - `windows`: Per-window-per-type matrix with done/pending/timed_out/failed states
    - `summary`: Per-type aggregated counts (done, timed_out, failed)
    - `in_progress`: Whether backfill is currently running (true for in_progress or retry_in_progress)
    - `retry_phase`: Whether the retry phase is currently active
    - `retry_type`: Data type currently being retried (null if not retrying)
    - `retry_window`: Window index being retried (null if not retrying)
    - `attempt_count`: Number of GC-and-retry cycles completed
    - `max_attempts`: Maximum GC-and-retry cycles before permanently failed (3)
    - `permanently_failed`: Whether backfill has exhausted all retry attempts

    **Window Cell States:**
    - `done`: Data received via webhook or Garmin API error (treated as done)
    - `pending`: Not yet processed
    - `timed_out`: No webhook received within timeout (warning)
    - `failed`: Permanently failed after retry attempt (error)
    """
    backfill_status = get_garmin_backfill_status(str(user_id))
    return {
        "user_id": str(user_id),
        "provider": "garmin",
        **backfill_status,
    }


@router.post("/garmin/users/{user_id}/backfill/cancel")
def cancel_garmin_backfill(
    user_id: UUID,
    _api_key: ApiKeyDep,
) -> dict[str, Any]:
    """
    Cancel an in-progress Garmin backfill for a user.

    Sets a cancellation flag in Redis. The backfill will stop after the
    current data type completes processing.

    Returns 409 if no backfill is currently in progress.
    """
    backfill_status = get_garmin_backfill_status(str(user_id))
    if backfill_status["overall_status"] not in ("in_progress", "retry_in_progress"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No backfill in progress for this user",
        )

    set_garmin_cancel_flag(str(user_id))

    return {
        "success": True,
        "user_id": str(user_id),
        "message": "Cancel requested. Backfill will stop after current type completes.",
    }


@router.post("/garmin/users/{user_id}/backfill/{type_name}/retry")
def retry_garmin_backfill_type(
    user_id: UUID,
    type_name: str,
    _api_key: ApiKeyDep,
) -> dict[str, Any]:
    """
    Retry backfill for a specific data type in the current window.

    Resets the type status to pending and triggers a new backfill attempt
    for the current window context. Use when a type has timed out or
    needs re-processing.

    **Valid Type Names:**
    sleeps, dailies, activities, activityDetails, hrv

    Returns:
        Dict with retry status
    """
    if type_name not in GARMIN_BACKFILL_DATA_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid type: {type_name}. Valid types: {', '.join(GARMIN_BACKFILL_DATA_TYPES)}",
        )

    # Reset the type status to pending and trigger backfill
    reset_garmin_type_status(str(user_id), type_name)
    trigger_garmin_backfill_for_type.delay(str(user_id), type_name)

    return {
        "success": True,
        "user_id": str(user_id),
        "type": type_name,
        "status": "triggered",
        "message": f"Retry triggered for {type_name}. Data will arrive via webhook.",
    }


# =============================================================================
# Historical Sync — user-initiated, provider-agnostic
# =============================================================================


@router.post("/{provider}/users/{user_id}/sync/historical")
def sync_historical_data(
    provider: Annotated[ProviderName, Path(description="Data provider")],
    user_id: UUID,
    _api_key: ApiKeyDep,
    days: Annotated[
        int,
        Query(
            description="Days of historical data to fetch (default: 90, max: 365). "
            "Ignored for providers with their own limits (e.g. Garmin: 30 days).",
            ge=1,
            le=365,
        ),
    ] = DEFAULT_HISTORICAL_DAYS,
) -> dict[str, Any]:
    """Trigger a historical sync of the user's data from a connected provider.

    Each provider strategy decides how to dispatch the sync (REST polling,
    webhook backfill, etc.). The ``days`` parameter may be ignored by
    providers that enforce their own limits.

    Historical sync is not automatically triggered when a provider is
    connected - it must be explicitly requested via this endpoint.
    (Changed in v0.4.2.)
    """
    strategy = factory.get_provider(provider.value)

    try:
        result = strategy.start_historical_sync(user_id, days)
    except UnsupportedProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.detail,
        )

    return {
        "success": True,
        "provider": provider.value,
        "user_id": str(user_id),
        "method": result.method,
        "task_id": result.task_id,
        "message": result.message,
        **({"days": result.days} if result.days is not None else {}),
        **({"start_date": result.start_date} if result.start_date is not None else {}),
        **({"end_date": result.end_date} if result.end_date is not None else {}),
    }
