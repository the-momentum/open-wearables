from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.database import DbSession
from app.schemas.taxonomy_common import Pagination
from app.schemas.taxonomy_events import (
    SleepSession,
    Workout,
)
from app.services import ApiKeyDep

router = APIRouter()


@router.get("/users/{user_id}/events/workouts")
async def list_workouts(
    user_id: UUID,
    start_date: str,
    end_date: str,
    db: DbSession,
    _api_key: ApiKeyDep,
    type: str | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, list[Workout] | Pagination]:
    """Returns workout sessions."""
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/users/{user_id}/events/sleep")
async def list_sleep_sessions(
    user_id: UUID,
    start_date: str,
    end_date: str,
    db: DbSession,
    _api_key: ApiKeyDep,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, list[SleepSession] | Pagination]:
    """Returns sleep sessions (including naps)."""
    raise HTTPException(status_code=501, detail="Not implemented")
