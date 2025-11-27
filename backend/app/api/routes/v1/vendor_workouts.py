from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Query

from app.database import DbSession
from app.services import ApiKeyDep
from app.services.garmin_service import garmin_service
from app.services.polar_service import polar_service
from app.services.suunto_service import suunto_service
from app.services import suunto_import_service


def parse_timestamp(value: str | None) -> int | None:
    """Parse timestamp from string (Unix timestamp or ISO 8601 date).

    Args:
        value: Unix timestamp as string or ISO 8601 date string

    Returns:
        Unix timestamp in seconds, or None if value is None
    """
    if not value:
        return None

    # Try to parse as integer (Unix timestamp)
    try:
        return int(value)
    except ValueError:
        pass

    # Try to parse as ISO 8601 date
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return int(dt.timestamp())
    except (ValueError, AttributeError) as e:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid timestamp format: {value}. "
                "Use Unix timestamp or ISO 8601 format (e.g., '2024-01-01T00:00:00Z')"
            ),
        ) from e


router = APIRouter()

# Map provider names to their service instances
WORKOUT_SERVICES = {
    "suunto": suunto_service,
    "polar": polar_service,
    "garmin": garmin_service,
}

ProviderType = Literal["suunto", "polar", "garmin"]


@router.get("/{provider}/users/{user_id}/workouts")
async def get_user_workouts(
    provider: Annotated[ProviderType, Path(description="Workout data provider (suunto, polar, garmin)")],
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
    service = WORKOUT_SERVICES.get(provider)

    if not service:
        raise HTTPException(status_code=400, detail=f"Provider '{provider}' not supported")

    if provider == "suunto":
        raw_workouts = service.get_workouts(
            db=db,
            user_id=user_id,
            since=since,
            limit=limit,
            offset=offset,
            filter_by_modification_time=filter_by_modification_time,
        )
        
        # temporary, for testing before services refactor
        suunto_import_service.load_data(db, raw_workouts, user_id)
        return raw_workouts

    if provider == "polar":
        return service.get_exercises(
            db=db,
            user_id=user_id,
            samples=samples,
            zones=zones,
            route=route,
        )

    # provider == "garmin"
    return service.get_activities(
        db=db,
        user_id=user_id,
        summary_start_time_in_seconds=parse_timestamp(summary_start_time),
        summary_end_time_in_seconds=parse_timestamp(summary_end_time),
    )


@router.get("/{provider}/users/{user_id}/workouts/{workout_id}")
async def get_user_workout_detail(
    provider: Annotated[ProviderType, Path(description="Workout data provider (suunto, polar, garmin)")],
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
    service = WORKOUT_SERVICES.get(provider)

    if not service:
        raise HTTPException(status_code=400, detail=f"Provider '{provider}' not supported")

    if provider == "suunto":
        return service.get_workout_detail(
            db=db,
            user_id=user_id,
            workout_key=workout_id,
        )

    if provider == "polar":
        return service.get_exercise_detail(
            db=db,
            user_id=user_id,
            exercise_id=workout_id,
            samples=samples,
            zones=zones,
            route=route,
        )

    # provider == "garmin"
    return service.get_activity_detail(
        db=db,
        user_id=user_id,
        activity_id=workout_id,
    )
