from datetime import datetime, timedelta
from enum import Enum
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Query, status

from app.database import DbSession
from app.integrations.celery.tasks import sync_vendor_data
from app.integrations.celery.tasks.garmin_backfill_task import (
    get_backfill_status,
    start_backfill,
)
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas.oauth import ProviderName
from app.services import ApiKeyDep
from app.services.providers.factory import ProviderFactory
from app.services.providers.templates.base_247_data import Base247DataTemplate

router = APIRouter()
factory = ProviderFactory()


class SyncDataType(str, Enum):
    """Types of data to sync from provider."""

    WORKOUTS = "workouts"
    DATA_247 = "247"  # Sleep, recovery, activity samples
    ALL = "all"


@router.post("/{provider}/users/{user_id}/sync")
async def sync_user_data(
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
    - **Garmin**: Workouts sync directly; 247 data (sleep, dailies, epochs) arrives via webhooks only
    - **Whoop**: Supports workouts and 247 data (sleep/recovery)

    **Execution Mode:**
    - `async=true` (default): Dispatches sync to background Celery worker. Returns immediately with task ID.
    - `async=false`: Executes synchronously (may timeout for large data sets).

    Requires valid API key and active connection for the user.
    """
    # Async mode: dispatch to Celery and return immediately
    if run_async:
        # For Garmin: Check if backfill is already in progress
        if provider.value == "garmin":
            backfill_status = get_backfill_status(str(user_id))
            if backfill_status["in_progress"]:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "message": "Garmin backfill already in progress. Please wait for completion.",
                        "backfill_status": backfill_status,
                    },
                )

            # Start backfill tracking for 1 year of history
            connection_repo = UserConnectionRepository()
            connection = connection_repo.get_by_user_and_provider(db, user_id, "garmin")
            if connection:
                start_backfill(str(user_id))

        # Convert since timestamp to ISO date if provided
        start_date_iso = None
        if since > 0:
            start_date_iso = datetime.fromtimestamp(since).isoformat()
        elif summary_start_time:
            start_date_iso = summary_start_time

        end_date_iso = summary_end_time  # May be None

        task = sync_vendor_data.delay(
            str(user_id),
            start_date=start_date_iso,
            end_date=end_date_iso,
            providers=[provider.value],
        )

        # Include backfill status in response for Garmin
        response: dict[str, Any] = {
            "success": True,
            "async": True,
            "task_id": task.id,
            "message": f"Sync task queued for {provider.value}. Check task status for results.",
        }
        if provider.value == "garmin":
            response["backfill_status"] = get_backfill_status(str(user_id))

        return response

    # Synchronous mode (original behavior)
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

    # Sync 247 data if requested (Suunto-specific)
    if data_type in (SyncDataType.DATA_247, SyncDataType.ALL):
        if strategy.data_247:
            data_provider = cast(Base247DataTemplate, strategy.data_247)
            start_dt = datetime.now() - timedelta(days=30)
            end_dt = datetime.now()

            if since:
                start_dt = datetime.fromtimestamp(since)

            # Use load_and_save_all if available (Suunto), otherwise fallback to load_all_247_data
            provider_any = cast(Any, data_provider)
            if hasattr(provider_any, "load_and_save_all"):
                results["data_247"] = provider_any.load_and_save_all(
                    db,
                    user_id,
                    start_time=start_dt,
                    end_time=end_dt,
                )
            else:
                results["data_247"] = provider_any.load_all_247_data(
                    db,
                    user_id,
                    start_time=start_dt,
                    end_time=end_dt,
                )
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


@router.get("/garmin/users/{user_id}/backfill-status")
async def get_garmin_backfill_status(
    user_id: UUID,
    _api_key: ApiKeyDep,
) -> dict[str, Any]:
    """
    Get Garmin backfill status for a user.

    Returns backfill progress including:
    - `in_progress`: Whether backfill is currently running
    - `months_completed`: Number of 30-day periods fetched (0-12)
    - `target_months`: Total months to fetch (12 = 1 year)
    - `current_end_date`: End date of last backfill period

    Use this to display progress in the UI during initial sync.
    """
    status = get_backfill_status(str(user_id))
    return {
        "user_id": str(user_id),
        "provider": "garmin",
        **status,
    }
