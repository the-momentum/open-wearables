"""Suunto-specific API routes for debugging and raw data access.

These endpoints provide direct access to Suunto API data for debugging
and verification of the normalization process.
"""

from datetime import datetime, timedelta, timezone
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.database import DbSession
from app.services import ApiKeyDep
from app.services.providers.factory import ProviderFactory
from app.services.providers.suunto import SuuntoStrategy

router = APIRouter(prefix="/suunto")
factory = ProviderFactory()


def _get_default_dates() -> tuple[datetime, datetime]:
    """Get default date range: 1 month ago to now."""
    now = datetime.now(timezone.utc)
    one_month_ago = now - timedelta(days=30)
    return one_month_ago, now


def _get_suunto_strategy() -> SuuntoStrategy:
    """Get Suunto strategy or raise error."""
    strategy = factory.get_provider("suunto")
    if not strategy:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Suunto provider not available",
        )
    return strategy


# -----------------------------------------------------------------------------
# Raw API Endpoints (for debugging - returns data directly from Suunto API)
# -----------------------------------------------------------------------------


@router.get("/users/{user_id}/raw/sleep")
async def get_raw_sleep_data(
    user_id: UUID,
    db: DbSession,
    _api_key: ApiKeyDep,
    from_time: Annotated[datetime | None, Query(description="Start time (ISO 8601). Default: 30 days ago")] = None,
    to_time: Annotated[datetime | None, Query(description="End time (ISO 8601). Default: now")] = None,
) -> list[dict[str, Any]]:
    """Get raw sleep data directly from Suunto API without normalization."""
    strategy = _get_suunto_strategy()
    if not strategy.data_247:
        raise HTTPException(status_code=501, detail="247 data not supported")

    default_from, default_to = _get_default_dates()
    from_time = from_time or default_from
    to_time = to_time or default_to

    return strategy.data_247.get_raw_sleep_data(db, user_id, from_time, to_time)


@router.get("/users/{user_id}/raw/recovery")
async def get_raw_recovery_data(
    user_id: UUID,
    db: DbSession,
    _api_key: ApiKeyDep,
    from_time: Annotated[datetime | None, Query(description="Start time (ISO 8601). Default: 30 days ago")] = None,
    to_time: Annotated[datetime | None, Query(description="End time (ISO 8601). Default: now")] = None,
) -> list[dict[str, Any]]:
    """Get raw recovery data directly from Suunto API without normalization."""
    strategy = _get_suunto_strategy()
    if not strategy.data_247:
        raise HTTPException(status_code=501, detail="247 data not supported")

    default_from, default_to = _get_default_dates()
    from_time = from_time or default_from
    to_time = to_time or default_to

    return strategy.data_247.get_raw_recovery_data(db, user_id, from_time, to_time)


@router.get("/users/{user_id}/raw/activity")
async def get_raw_activity_samples(
    user_id: UUID,
    db: DbSession,
    _api_key: ApiKeyDep,
    from_time: Annotated[datetime | None, Query(description="Start time (ISO 8601). Default: 30 days ago")] = None,
    to_time: Annotated[datetime | None, Query(description="End time (ISO 8601). Default: now")] = None,
) -> list[dict[str, Any]]:
    """Get raw activity samples directly from Suunto API without normalization."""
    strategy = _get_suunto_strategy()
    if not strategy.data_247:
        raise HTTPException(status_code=501, detail="247 data not supported")

    default_from, default_to = _get_default_dates()
    from_time = from_time or default_from
    to_time = to_time or default_to

    return strategy.data_247.get_raw_activity_samples(db, user_id, from_time, to_time)


@router.get("/users/{user_id}/raw/daily-statistics")
async def get_raw_daily_statistics(
    user_id: UUID,
    db: DbSession,
    _api_key: ApiKeyDep,
    start_date: Annotated[datetime | None, Query(description="Start date (ISO 8601). Default: 30 days ago")] = None,
    end_date: Annotated[datetime | None, Query(description="End date (ISO 8601). Default: now")] = None,
) -> list[dict[str, Any]]:
    """Get raw daily activity statistics directly from Suunto API."""
    strategy = _get_suunto_strategy()
    if not strategy.data_247:
        raise HTTPException(status_code=501, detail="247 data not supported")

    default_from, default_to = _get_default_dates()
    start_date = start_date or default_from
    end_date = end_date or default_to

    return strategy.data_247.get_daily_activity_statistics(db, user_id, start_date, end_date)


@router.get("/users/{user_id}/raw/workouts")
async def get_raw_workouts(
    user_id: UUID,
    db: DbSession,
    _api_key: ApiKeyDep,
    since: Annotated[int, Query(description="Unix timestamp in milliseconds")] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    """Get raw workouts directly from Suunto API."""
    strategy = _get_suunto_strategy()
    if not strategy.workouts:
        raise HTTPException(status_code=501, detail="Workouts not supported")
    return strategy.workouts.get_workouts_from_api(db, user_id, since=since, limit=limit, offset=offset)


@router.get("/users/{user_id}/raw/workouts/{workout_key}")
async def get_raw_workout_detail(
    user_id: UUID,
    workout_key: str,
    db: DbSession,
    _api_key: ApiKeyDep,
) -> dict[str, Any]:
    """Get raw workout detail directly from Suunto API."""
    strategy = _get_suunto_strategy()
    if not strategy.workouts:
        raise HTTPException(status_code=501, detail="Workouts not supported")
    return strategy.workouts.get_workout_detail_from_api(db, user_id, workout_key)


# -----------------------------------------------------------------------------
# Normalized Data Endpoints (returns data after our normalization)
# -----------------------------------------------------------------------------


@router.get("/users/{user_id}/normalized/sleep")
async def get_normalized_sleep_data(
    user_id: UUID,
    db: DbSession,
    _api_key: ApiKeyDep,
    from_time: Annotated[datetime | None, Query(description="Start time (ISO 8601). Default: 30 days ago")] = None,
    to_time: Annotated[datetime | None, Query(description="End time (ISO 8601). Default: now")] = None,
) -> list[dict[str, Any]]:
    """Get sleep data with our normalization applied (for comparison with raw)."""
    strategy = _get_suunto_strategy()
    if not strategy.data_247:
        raise HTTPException(status_code=501, detail="247 data not supported")

    default_from, default_to = _get_default_dates()
    from_time = from_time or default_from
    to_time = to_time or default_to

    return strategy.data_247.process_sleep_data(db, user_id, from_time, to_time)


@router.get("/users/{user_id}/normalized/recovery")
async def get_normalized_recovery_data(
    user_id: UUID,
    db: DbSession,
    _api_key: ApiKeyDep,
    from_time: Annotated[datetime | None, Query(description="Start time (ISO 8601). Default: 30 days ago")] = None,
    to_time: Annotated[datetime | None, Query(description="End time (ISO 8601). Default: now")] = None,
) -> list[dict[str, Any]]:
    """Get recovery data with our normalization applied."""
    strategy = _get_suunto_strategy()
    if not strategy.data_247:
        raise HTTPException(status_code=501, detail="247 data not supported")

    default_from, default_to = _get_default_dates()
    from_time = from_time or default_from
    to_time = to_time or default_to

    return strategy.data_247.process_recovery_data(db, user_id, from_time, to_time)


@router.get("/users/{user_id}/normalized/activity")
async def get_normalized_activity_samples(
    user_id: UUID,
    db: DbSession,
    _api_key: ApiKeyDep,
    from_time: Annotated[datetime | None, Query(description="Start time (ISO 8601). Default: 30 days ago")] = None,
    to_time: Annotated[datetime | None, Query(description="End time (ISO 8601). Default: now")] = None,
) -> dict[str, list[dict[str, Any]]]:
    """Get activity samples with our normalization applied (categorized by type)."""
    strategy = _get_suunto_strategy()
    if not strategy.data_247:
        raise HTTPException(status_code=501, detail="247 data not supported")

    default_from, default_to = _get_default_dates()
    from_time = from_time or default_from
    to_time = to_time or default_to

    return strategy.data_247.process_activity_samples(db, user_id, from_time, to_time)


# -----------------------------------------------------------------------------
# Sync Endpoints (load data from Suunto and save to our database)
# -----------------------------------------------------------------------------


@router.post("/users/{user_id}/sync/all")
async def sync_all_suunto_data(
    user_id: UUID,
    db: DbSession,
    _api_key: ApiKeyDep,
    from_time: Annotated[datetime | None, Query(description="Start time (ISO 8601). Default: 30 days ago")] = None,
    to_time: Annotated[datetime | None, Query(description="End time (ISO 8601). Default: now")] = None,
    include_workouts: Annotated[bool, Query(description="Include workouts sync")] = True,
    include_sleep: Annotated[bool, Query(description="Include sleep sync")] = True,
    include_recovery: Annotated[bool, Query(description="Include recovery sync")] = False,
    include_activity: Annotated[bool, Query(description="Include activity samples sync")] = False,
) -> dict[str, Any]:
    """Synchronize all Suunto data types for a user.

    This endpoint fetches data from Suunto API and saves it to our database.
    Use this for manual sync or testing. For automated sync, use Celery tasks.
    """
    strategy = _get_suunto_strategy()

    default_from, default_to = _get_default_dates()
    from_time = from_time or default_from
    to_time = to_time or default_to
    results = {
        "workouts_synced": 0,
        "sleep_sessions_synced": 0,
        "recovery_samples_synced": 0,
        "activity_samples_synced": 0,
        "errors": [],
    }

    # Sync workouts
    if include_workouts and strategy.workouts:
        try:
            since_ms = int(from_time.timestamp() * 1000)
            success = strategy.workouts.load_data(db, user_id, since=since_ms)
            results["workouts_synced"] = 1 if success else 0
        except Exception as e:
            results["errors"].append(f"Workouts: {str(e)}")

    # Sync 247 data
    if strategy.data_247:
        if include_sleep:
            try:
                count = strategy.data_247.load_and_save_sleep(db, user_id, from_time, to_time)
                results["sleep_sessions_synced"] = count
            except Exception as e:
                results["errors"].append(f"Sleep: {str(e)}")

        # Recovery and activity saving not fully implemented yet
        # They can be viewed via normalized endpoints for now

    return results


@router.post("/users/{user_id}/sync/sleep")
async def sync_suunto_sleep(
    user_id: UUID,
    db: DbSession,
    _api_key: ApiKeyDep,
    from_time: Annotated[datetime | None, Query(description="Start time (ISO 8601). Default: 30 days ago")] = None,
    to_time: Annotated[datetime | None, Query(description="End time (ISO 8601). Default: now")] = None,
) -> dict[str, int]:
    """Synchronize only sleep data from Suunto."""
    strategy = _get_suunto_strategy()
    if not strategy.data_247:
        raise HTTPException(status_code=501, detail="247 data not supported")

    default_from, default_to = _get_default_dates()
    from_time = from_time or default_from
    to_time = to_time or default_to

    count = strategy.data_247.load_and_save_sleep(db, user_id, from_time, to_time)
    return {"sleep_sessions_synced": count}


@router.post("/users/{user_id}/sync/workouts")
async def sync_suunto_workouts(
    user_id: UUID,
    db: DbSession,
    _api_key: ApiKeyDep,
    since: Annotated[int, Query(description="Unix timestamp in milliseconds")] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, bool]:
    """Synchronize only workouts from Suunto."""
    strategy = _get_suunto_strategy()
    if not strategy.workouts:
        raise HTTPException(status_code=501, detail="Workouts not supported")

    success = strategy.workouts.load_data(db, user_id, since=since, limit=limit)
    return {"success": success}
