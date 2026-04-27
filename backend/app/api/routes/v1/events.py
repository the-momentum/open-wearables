from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.database import DbSession
from app.schemas.model_crud.activities import EventRecordQueryParams
from app.schemas.responses.activity import (
    SleepSession,
    Workout,
)
from app.schemas.utils import PaginatedResponse
from app.services import ApiKeyDep
from app.services.event_record_service import event_record_service
from app.utils.dates import parse_query_datetime

router = APIRouter()


@router.get("/users/{user_id}/events/workouts")
def list_workouts(
    user_id: UUID,
    start_date: str,
    end_date: str,
    db: DbSession,
    _api_key: ApiKeyDep,
    record_type: str | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> PaginatedResponse[Workout]:
    """Returns workout sessions."""
    params = EventRecordQueryParams(
        start_datetime=parse_query_datetime(start_date),
        end_datetime=parse_query_datetime(end_date),
        cursor=cursor,
        limit=limit,
        record_type=record_type,
    )
    return event_record_service.get_workouts(db, user_id, params)


@router.get("/users/{user_id}/events/sleep")
def list_sleep_sessions(
    user_id: UUID,
    start_date: str,
    end_date: str,
    db: DbSession,
    _api_key: ApiKeyDep,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> PaginatedResponse[SleepSession]:
    """Returns sleep sessions (including naps)."""
    params = EventRecordQueryParams(
        start_datetime=parse_query_datetime(start_date),
        end_datetime=parse_query_datetime(end_date),
        cursor=cursor,
        limit=limit,
    )
    return event_record_service.get_sleep_sessions(db, user_id, params)


@router.delete("/users/{user_id}/events/workouts/{workout_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workout(
    user_id: UUID,
    workout_id: UUID,
    db: DbSession,
    _api_key: ApiKeyDep,
) -> None:
    """Delete a workout session."""
    if not event_record_service.delete_event_record(db, user_id, workout_id, "workout"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workout not found")


@router.delete("/users/{user_id}/events/sleep/{sleep_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sleep_session(
    user_id: UUID,
    sleep_id: UUID,
    db: DbSession,
    _api_key: ApiKeyDep,
) -> None:
    """Delete a sleep session."""
    if not event_record_service.delete_event_record(db, user_id, sleep_id, "sleep"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sleep session not found")
