from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query

from app.schemas.taxonomy_common import Pagination
from app.schemas.taxonomy_events import (
    Meal,
    Measurement,
    SleepSession,
    Workout,
    WorkoutDetailed,
)

router = APIRouter()


@router.get("/users/{user_id}/events/workouts")
async def list_workouts(
    user_id: UUID,
    start_date: date,
    end_date: date,
    type: str | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, list[Workout] | Pagination]:
    """Returns workout sessions."""
    # TODO: Implement service call
    return {"data": [], "pagination": Pagination(has_more=False)}


@router.get("/users/{user_id}/events/workouts/{workout_id}")
async def get_workout(
    user_id: UUID,
    workout_id: UUID,
    include_samples: bool = False,
) -> WorkoutDetailed:
    """Returns detailed workout data."""
    # TODO: Implement service call
    # Return dummy data to satisfy type checker if needed, or raise NotImplementedError
    raise NotImplementedError("Service not implemented")


@router.get("/users/{user_id}/events/sleep")
async def list_sleep_sessions(
    user_id: UUID,
    start_date: date,
    end_date: date,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, list[SleepSession] | Pagination]:
    """Returns sleep sessions (including naps)."""
    # TODO: Implement service call
    return {"data": [], "pagination": Pagination(has_more=False)}


@router.get("/users/{user_id}/events/meals")
async def list_meals(
    user_id: UUID,
    start_date: date,
    end_date: date,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, list[Meal] | Pagination]:
    """Returns logged meals."""
    # TODO: Implement service call
    return {"data": [], "pagination": Pagination(has_more=False)}


@router.get("/users/{user_id}/events/measurements")
async def list_measurements(
    user_id: UUID,
    start_date: date,
    end_date: date,
    type: Literal["weight", "blood_pressure", "body_composition", "temperature", "blood_glucose"] | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, list[Measurement] | Pagination]:
    """Returns discrete health measurements."""
    # TODO: Implement service call
    return {"data": [], "pagination": Pagination(has_more=False)}
