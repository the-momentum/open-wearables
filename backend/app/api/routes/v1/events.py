from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.database import DbSession
from app.schemas.common_types import PaginatedResponse
from app.schemas.event_record import EventRecordQueryParams
from app.schemas.events import (
    SleepSession,
    Workout,
)
from app.services import ApiKeyDep
from app.services.event_record_service import event_record_service
from app.utils.dates import parse_query_datetime

router = APIRouter()


@router.get("/users/{user_id}/events/workouts")
async def list_workouts(
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
    return await event_record_service.get_workouts(db, user_id, params)


@router.get("/users/{user_id}/events/sleep")
async def list_sleep_sessions(
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
    return await event_record_service.get_sleep_sessions(db, user_id, params)
