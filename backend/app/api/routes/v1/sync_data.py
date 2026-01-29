import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Query, status

from app.database import DbSession
from app.integrations.celery.tasks import (
    GARMIN_BACKFILL_DATA_TYPES,
    get_garmin_backfill_status,
    reset_garmin_type_status,
    sync_vendor_data,
    trigger_garmin_backfill_for_type,
)
from app.integrations.celery.tasks.garmin_summary_sync_task import (
    cancel_sync as cancel_summary_sync,
)
from app.integrations.celery.tasks.garmin_summary_sync_task import (
    get_sync_status as get_summary_sync_status,
)
from app.integrations.celery.tasks.garmin_summary_sync_task import (
    start_garmin_summary_sync,
)
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas.oauth import ProviderName
from app.services import ApiKeyDep
from app.services.providers.factory import ProviderFactory
from app.services.providers.garmin.summary import GarminSummaryService
from app.services.providers.templates.base_247_data import Base247DataTemplate

logger = logging.getLogger(__name__)

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
    - **Garmin**: Uses REST Summary endpoints for immediate data sync
    - **Whoop**: Supports workouts and 247 data (sleep/recovery)

    **Execution Mode:**
    - `async=true` (default): Dispatches sync to background Celery worker. Returns immediately with task ID.
    - `async=false`: Executes synchronously (may timeout for large data sets).

    Requires valid API key and active connection for the user.
    """
    # Async mode: dispatch to Celery and return immediately
    if run_async:
        # For Garmin: Check if summary sync is already in progress
        if provider.value == "garmin":
            sync_status = get_summary_sync_status(str(user_id))
            if sync_status["status"] in ("SYNCING", "WAITING"):
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "message": "Garmin sync already in progress. Please wait for completion.",
                        "sync_status": sync_status,
                    },
                )

            # Fetch immediate data (last 7 days) via Summary endpoints
            connection_repo = UserConnectionRepository()
            connection = connection_repo.get_by_user_and_provider(db, user_id, "garmin")

            summary_result: dict[str, Any] | None = None
            if connection:
                try:
                    logger.info(f"Fetching Garmin summary data for user {user_id}")
                    summary_service = GarminSummaryService()
                    summary_result = summary_service.fetch_and_save_all_summaries(
                        db=db,
                        user_id=user_id,
                        days=7,  # Last 7 days via Summary API
                    )
                    logger.info(f"Garmin summary fetch complete: {summary_result.get('total_saved', 0)} records saved")
                except Exception as e:
                    logger.warning(f"Failed to fetch Garmin summary data: {e}")
                    summary_result = {"error": str(e)}

        # Convert since timestamp to ISO date if provided
        start_date_iso = None
        if since > 0:
            start_date_iso = datetime.fromtimestamp(since).isoformat()
        elif summary_start_time:
            start_date_iso = summary_start_time

        end_date_iso = summary_end_time  # May be None

        task = sync_vendor_data.delay(
            user_id=str(user_id),
            start_date=start_date_iso,
            end_date=end_date_iso,
            providers=[provider.value],
        )

        # Include sync status and summary result in response for Garmin
        response: dict[str, Any] = {
            "success": True,
            "async": True,
            "task_id": task.id,
            "message": f"Sync task queued for {provider.value}. Check task status for results.",
        }
        if provider.value == "garmin":
            response["sync_status"] = get_summary_sync_status(str(user_id))
            if summary_result:
                response["summary_result"] = summary_result
                response["message"] = "Garmin data (last 7 days) synced successfully."

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


# =============================================================================
# Garmin Summary Sync Endpoints (REST-based, 365-day sync)
# =============================================================================


@router.post("/garmin/users/{user_id}/summary-sync")
async def start_garmin_summary_fetch(
    user_id: UUID,
    db: DbSession,
    _api_key: ApiKeyDep,
    resume: Annotated[
        bool,
        Query(description="Resume interrupted sync from last position"),
    ] = False,
) -> dict[str, Any]:
    """
    Start 365-day Garmin summary sync via REST endpoints.

    This endpoint initiates a background sync process that fetches historical
    Garmin data using the REST Summary endpoints. Unlike the webhook-based
    backfill, this approach:

    - Fetches data directly via HTTP (no webhook setup required)
    - Supports 365 days of historical data (vs 90 days for backfill)
    - Includes 16 data types (vs 5 for backfill)
    - Supports pause/resume functionality

    **Rate Limiting:**
    The sync process respects Garmin's rate limits by adding delays between
    requests (3 minutes default, 10 minutes for HRV).

    **Progress:**
    Use GET /garmin/users/{user_id}/summary-sync/status to monitor progress.

    **Estimated Time:**
    Full sync takes ~12 days due to rate limiting (365 days x 16 types x 3 min).

    Args:
        user_id: User UUID with active Garmin connection
        resume: If True, resume from last position. If False, start fresh.

    Returns:
        Dict with sync initialization status
    """
    # Verify Garmin connection exists
    connection_repo = UserConnectionRepository()
    connection = connection_repo.get_by_user_and_provider(db, user_id, "garmin")

    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Garmin connection found for user",
        )

    # Check if already syncing (unless resuming)
    current_status = get_summary_sync_status(str(user_id))
    if current_status["status"] in ("SYNCING", "WAITING") and not resume:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "message": "Garmin summary sync already in progress. Use resume=true to continue.",
                "sync_status": current_status,
            },
        )

    # Start async sync task
    task = start_garmin_summary_sync.delay(str(user_id), resume=resume)

    logger.info(f"Started Garmin summary sync for user {user_id} (task_id={task.id}, resume={resume})")

    return {
        "success": True,
        "task_id": task.id,
        "message": f"Garmin summary sync {'resumed' if resume else 'started'}. Check status endpoint for progress.",
        "sync_status": get_summary_sync_status(str(user_id)),
    }


@router.get("/garmin/users/{user_id}/summary-sync/status")
async def get_garmin_summary_sync_status(
    user_id: UUID,
    _api_key: ApiKeyDep,
) -> dict[str, Any]:
    """
    Get Garmin summary sync status for a user.

    Returns sync progress including:
    - `status`: IDLE | SYNCING | WAITING | COMPLETED | FAILED
    - `progress_percent`: Overall progress (0-100)
    - `current_data_type`: Current data type being synced
    - `current_type_index`: Index of current type (0-15)
    - `total_types`: Total data types (16)
    - `current_day`: Current day being processed (0-364)
    - `target_days`: Total days to sync (365)
    - `started_at`: ISO timestamp when sync started
    - `last_chunk_at`: ISO timestamp of last successful chunk
    - `errors`: List of recent errors (max 10)

    **Status Meanings:**
    - IDLE: No sync in progress
    - SYNCING: Currently fetching data
    - WAITING: Paused between requests (rate limiting)
    - COMPLETED: Sync finished successfully
    - FAILED: Sync stopped due to errors
    """
    sync_status = get_summary_sync_status(str(user_id))
    return {
        "user_id": str(user_id),
        "provider": "garmin",
        **sync_status,
    }


@router.delete("/garmin/users/{user_id}/summary-sync")
async def cancel_garmin_summary_sync(
    user_id: UUID,
    _api_key: ApiKeyDep,
) -> dict[str, Any]:
    """
    Cancel in-progress Garmin summary sync.

    Stops the sync process gracefully. The sync can be resumed later
    using POST /garmin/users/{user_id}/summary-sync?resume=true.

    Returns:
        Dict with cancellation status
    """
    result = cancel_summary_sync(str(user_id))

    if result.get("cancelled"):
        logger.info(f"Cancelled Garmin summary sync for user {user_id}")
    else:
        logger.debug(f"No active sync to cancel for user {user_id}")

    return {
        "user_id": str(user_id),
        "provider": "garmin",
        **result,
    }


# =============================================================================
# Garmin Backfill Endpoints (webhook-based, 90-day sync)
# =============================================================================


@router.get("/garmin/users/{user_id}/backfill/status")
async def get_garmin_backfill_status_endpoint(
    user_id: UUID,
    _api_key: ApiKeyDep,
) -> dict[str, Any]:
    """
    Get Garmin backfill status for all 16 data types.

    The backfill is webhook-based and auto-triggered after OAuth connection.
    Returns status for each data type independently.

    **Response Fields:**
    - `overall_status`: pending | in_progress | complete | partial
    - `types`: Object with status for each of 16 data types
    - `success_count`: Number of successfully synced types
    - `failed_count`: Number of failed types (can be retried)
    - `pending_count`: Number of types not yet triggered
    - `triggered_count`: Number of types currently in progress

    **Type Status:**
    - `pending`: Not yet triggered
    - `triggered`: Backfill request sent, waiting for webhook
    - `success`: Data received via webhook
    - `failed`: Error occurred (can retry)
    """
    backfill_status = get_garmin_backfill_status(str(user_id))
    return {
        "user_id": str(user_id),
        "provider": "garmin",
        **backfill_status,
    }


@router.post("/garmin/users/{user_id}/backfill/{type_name}/retry")
async def retry_garmin_backfill_type(
    user_id: UUID,
    type_name: str,
    _api_key: ApiKeyDep,
) -> dict[str, Any]:
    """
    Retry backfill for a specific failed data type.

    Use this endpoint to retry fetching historical data for a type that failed.

    **Valid Type Names:**
    sleeps, dailies, epochs, bodyComps, hrv, activities, activityDetails,
    moveiq, healthSnapshot, stressDetails, respiration, pulseOx,
    bloodPressures, userMetrics, skinTemp, mct

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
