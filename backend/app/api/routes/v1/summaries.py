from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.database import DbSession
from app.schemas.common_types import Pagination
from app.schemas.summaries import (
    ActivitySummary,
    BodySummary,
    RecoverySummary,
    SleepSummary,
)
from app.services import ApiKeyDep

router = APIRouter()


@router.get("/users/{user_id}/summaries/activity")
async def get_activity_summary(
    user_id: UUID,
    start_date: str,
    end_date: str,
    db: DbSession,
    _api_key: ApiKeyDep,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, list[ActivitySummary] | Pagination]:
    """Returns daily aggregated activity metrics."""
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/users/{user_id}/summaries/sleep")
async def get_sleep_summary(
    user_id: UUID,
    start_date: str,
    end_date: str,
    db: DbSession,
    _api_key: ApiKeyDep,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, list[SleepSummary] | Pagination]:
    """Returns daily sleep metrics."""
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/users/{user_id}/summaries/recovery")
async def get_recovery_summary(
    user_id: UUID,
    start_date: str,
    end_date: str,
    db: DbSession,
    _api_key: ApiKeyDep,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, list[RecoverySummary] | Pagination]:
    """Returns daily recovery metrics (Sleep + HRV + RHR)."""
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/users/{user_id}/summaries/body")
async def get_body_summary(
    user_id: UUID,
    start_date: str,
    end_date: str,
    db: DbSession,
    _api_key: ApiKeyDep,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, list[BodySummary] | Pagination]:
    """Returns daily body metrics."""
    raise HTTPException(status_code=501, detail="Not implemented")
