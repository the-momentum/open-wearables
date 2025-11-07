from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.database import DbSession
from app.services import ApiKeyDep
from app.services.suunto_service import suunto_service

router = APIRouter()


@router.get("/users/{user_id}/workouts")
async def get_suunto_workouts(
    user_id: UUID,
    db: DbSession,
    _api_key: ApiKeyDep,
    since: Annotated[int, Query(description="Unix timestamp to get workouts since (0 = all)")] = 0,
    limit: Annotated[int, Query(description="Maximum number of workouts (max 100)", le=100)] = 50,
    offset: Annotated[int, Query(description="Offset for pagination")] = 0,
    filter_by_modification_time: Annotated[
        bool,
        Query(description="Filter by modification time instead of creation time"),
    ] = True,
) -> dict:
    """
    Get workouts from Suunto API for a specific user.

    Requires valid API key and active Suunto connection for the user.
    """
    return suunto_service.get_workouts(
        db=db,
        user_id=user_id,
        since=since,
        limit=limit,
        offset=offset,
        filter_by_modification_time=filter_by_modification_time,
    )


@router.get("/users/{user_id}/workouts/{workout_key}")
async def get_suunto_workout_detail(
    user_id: UUID,
    workout_key: str,
    db: DbSession,
    _api_key: ApiKeyDep,
) -> dict:
    """
    Get detailed workout data from Suunto API.

    Requires valid API key and active Suunto connection for the user.
    """
    return suunto_service.get_workout_detail(db=db, user_id=user_id, workout_key=workout_key)
