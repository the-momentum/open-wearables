from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.database import DbSession
from app.schemas import EventRecordQueryParams
from app.schemas.taxonomy_common import Pagination
from app.schemas.taxonomy_events import (
    Meal,
    Measurement,
    SleepSession,
    Workout,
    WorkoutDetailed,
)
from app.services import ApiKeyDep, event_record_service

router = APIRouter()


@router.get("/users/{user_id}/events/workouts")
async def list_workouts(
    user_id: UUID,
    start_date: date,
    end_date: date,
    db: DbSession,
    _api_key: ApiKeyDep,
    type: str | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, list[Workout] | Pagination]:
    """Returns workout sessions."""
    params = EventRecordQueryParams(
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        record_type=type,
        limit=limit,
        offset=0,  # TODO: Implement cursor pagination properly
    )
    return await event_record_service.get_workouts(db, user_id, params)


@router.get("/users/{user_id}/events/workouts/{workout_id}")
async def get_workout(
    user_id: UUID,
    workout_id: UUID,
    db: DbSession,
    _api_key: ApiKeyDep,
    include_samples: bool = False,
) -> WorkoutDetailed:
    """Returns detailed workout data."""
    workout = await event_record_service.get_workout_detailed(db, user_id, workout_id)
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")
    return workout


@router.get("/users/{user_id}/events/sleep")
async def list_sleep_sessions(
    user_id: UUID,
    start_date: date,
    end_date: date,
    db: DbSession,
    _api_key: ApiKeyDep,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, list[SleepSession] | Pagination]:
    """Returns sleep sessions (including naps)."""
    params = EventRecordQueryParams(
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        limit=limit,
        offset=0,
    )
    return await event_record_service.get_sleep_sessions(db, user_id, params)


@router.get("/users/{user_id}/events/meals")
async def list_meals(
    user_id: UUID,
    start_date: date,
    end_date: date,
    db: DbSession,
    _api_key: ApiKeyDep,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, list[Meal] | Pagination]:
    """Returns logged meals."""
    params = EventRecordQueryParams(
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        limit=limit,
        offset=0,
    )
    return await event_record_service.get_meals(db, user_id, params)


@router.get("/users/{user_id}/events/measurements")
async def list_measurements(
    user_id: UUID,
    start_date: date,
    end_date: date,
    db: DbSession,
    _api_key: ApiKeyDep,
    type: Literal["weight", "blood_pressure", "body_composition", "temperature", "blood_glucose"] | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, list[Measurement] | Pagination]:
    """Returns discrete health measurements."""
    params = EventRecordQueryParams(
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        record_type=type,
        limit=limit,
        offset=0,
    )
    return await event_record_service.get_measurements(db, user_id, params)
