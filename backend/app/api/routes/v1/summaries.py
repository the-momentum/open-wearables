from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.database import DbSession
from app.schemas.common_types import PaginatedResponse
from app.schemas.summaries import (
    ActivitySummary,
    BodySummary,
    RecoverySummary,
    SleepSummary,
)
from app.services import ApiKeyDep
from app.services.summaries_service import summaries_service
from app.utils.dates import parse_query_datetime

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
) -> PaginatedResponse[ActivitySummary]:
    """Returns daily aggregated activity metrics.

    Aggregates time-series data (steps, energy, heart rate, etc.) by day.
    """
    start_datetime = parse_query_datetime(start_date)
    end_datetime = parse_query_datetime(end_date)
    return await summaries_service.get_activity_summaries(db, user_id, start_datetime, end_datetime, cursor, limit)


@router.get("/users/{user_id}/summaries/sleep")
async def get_sleep_summary(
    user_id: UUID,
    start_date: str,
    end_date: str,
    db: DbSession,
    _api_key: ApiKeyDep,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> PaginatedResponse[SleepSummary]:
    """Returns daily sleep metrics."""
    start_datetime = parse_query_datetime(start_date)
    end_datetime = parse_query_datetime(end_date)
    return await summaries_service.get_sleep_summaries(db, user_id, start_datetime, end_datetime, cursor, limit)


@router.get("/users/{user_id}/summaries/recovery")
async def get_recovery_summary(
    user_id: UUID,
    start_date: str,
    end_date: str,
    db: DbSession,
    _api_key: ApiKeyDep,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> PaginatedResponse[RecoverySummary]:
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
) -> PaginatedResponse[BodySummary]:
    """Returns daily body composition and vital statistics.

    Aggregates include:
    - Body composition: weight, height, body fat %, muscle mass, BMI
    - Vitals (7-day rolling avg): resting HR, HRV, blood pressure
    - Static: age (calculated from birth date)
    """
    start_datetime = parse_query_datetime(start_date)
    end_datetime = parse_query_datetime(end_date)
    return await summaries_service.get_body_summaries(db, user_id, start_datetime, end_datetime, cursor, limit)
