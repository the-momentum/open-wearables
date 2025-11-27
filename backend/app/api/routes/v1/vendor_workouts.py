from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, Query

from app.database import DbSession
from app.schemas.oauth import ProviderName
from app.services import ApiKeyDep
from app.services.providers.factory import ProviderFactory


router = APIRouter()
factory = ProviderFactory()


@router.get("/{provider}/users/{user_id}/workouts")
async def get_user_workouts(
    provider: Annotated[ProviderName, Path(description="Workout data provider")],
    user_id: UUID,
    db: DbSession,
    _api_key: ApiKeyDep,
    # Suunto-specific parameters
    since: Annotated[
        int,
        Query(description="Unix timestamp to get workouts since (0 = all, Suunto only)"),
    ] = 0,
    limit: Annotated[
        int,
        Query(description="Maximum number of workouts (Suunto: max 100)", le=100),
    ] = 50,
    offset: Annotated[int, Query(description="Offset for pagination (Suunto only)")] = 0,
    filter_by_modification_time: Annotated[
        bool,
        Query(description="Filter by modification time instead of creation time (Suunto only)"),
    ] = True,
    # Polar-specific parameters
    samples: Annotated[bool, Query(description="Return sample data (Polar only)")] = False,
    zones: Annotated[bool, Query(description="Return zones data (Polar only)")] = False,
    route: Annotated[bool, Query(description="Return route data (Polar only)")] = False,
    # Garmin-specific parameters (backfill API - no pull token required)
    summary_start_time: Annotated[
        str | None,
        Query(description="Activity start time as Unix timestamp or ISO 8601 date (Garmin only)"),
    ] = None,
    summary_end_time: Annotated[
        str | None,
        Query(description="Activity end time as Unix timestamp or ISO 8601 date (Garmin only)"),
    ] = None,
) -> dict | list[dict]:
    """
    Get workouts/exercises/activities from fitness provider API for a specific user.

    - **Suunto**: Returns workouts with pagination support
    - **Polar**: Returns exercises (Polar's term for workouts)
    - **Garmin**: Returns activities from Health API

    Requires valid API key and active connection for the user.
    """
    strategy = factory.get_provider(provider.value)

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

    return strategy.workouts.get_workouts_from_api(db, user_id, **params)


@router.get("/{provider}/users/{user_id}/workouts/{workout_id}")
async def get_user_workout_detail(
    provider: Annotated[ProviderName, Path(description="Workout data provider")],
    user_id: UUID,
    workout_id: str,
    db: DbSession,
    _api_key: ApiKeyDep,
    # Polar-specific parameters
    samples: Annotated[bool, Query(description="Return sample data (Polar only)")] = False,
    zones: Annotated[bool, Query(description="Return zones data (Polar only)")] = False,
    route: Annotated[bool, Query(description="Return route data (Polar only)")] = False,
) -> dict:
    """
    Get detailed workout/exercise/activity data from fitness provider API.

    - **Suunto**: Returns detailed workout data
    - **Polar**: Returns detailed exercise data
    - **Garmin**: Returns detailed activity data

    Requires valid API key and active connection for the user.
    """
    strategy = factory.get_provider(provider.value)

    # Collect all parameters
    params = {
        "samples": samples,
        "zones": zones,
        "route": route,
    }

    return strategy.workouts.get_workout_detail_from_api(db, user_id, workout_id, **params)
