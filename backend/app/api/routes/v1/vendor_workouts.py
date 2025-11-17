from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Query

from app.database import DbSession
from app.services import ApiKeyDep
from app.services.polar_service import polar_service
from app.services.suunto_service import suunto_service

router = APIRouter()

# Map provider names to their service instances
WORKOUT_SERVICES = {
    "suunto": suunto_service,
    "polar": polar_service,
}

ProviderType = Literal["suunto", "polar"]


@router.get("/{provider}/users/{user_id}/workouts")
async def get_user_workouts(
    provider: Annotated[ProviderType, Path(description="Workout data provider (suunto, polar)")],
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
) -> dict | list[dict]:
    """
    Get workouts/exercises from fitness provider API for a specific user.

    - **Suunto**: Returns workouts with pagination support
    - **Polar**: Returns exercises (Polar's term for workouts)

    Requires valid API key and active connection for the user.
    """
    service = WORKOUT_SERVICES.get(provider)

    if not service:
        raise HTTPException(status_code=400, detail=f"Provider '{provider}' not supported")

    if provider == "suunto":
        return service.get_workouts(
            db=db,
            user_id=user_id,
            since=since,
            limit=limit,
            offset=offset,
            filter_by_modification_time=filter_by_modification_time,
        )

    # provider == "polar"
    return service.get_exercises(
        db=db,
        user_id=user_id,
        samples=samples,
        zones=zones,
        route=route,
    )


@router.get("/{provider}/users/{user_id}/workouts/{workout_id}")
async def get_user_workout_detail(
    provider: Annotated[ProviderType, Path(description="Workout data provider (suunto, polar)")],
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
    Get detailed workout/exercise data from fitness provider API.

    - **Suunto**: Returns detailed workout data
    - **Polar**: Returns detailed exercise data

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

    # provider == "polar"
    return service.get_exercise_detail(
        db=db,
        user_id=user_id,
        exercise_id=workout_id,
        samples=samples,
        zones=zones,
        route=route,
    )
