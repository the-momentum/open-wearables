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
    limit: Annotated[int, Query(ge=1, le=400)] = 50,
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
    db: DbSession,
    _api_key: ApiKeyDep,
    average_period: Annotated[int, Query(ge=1, le=7, description="Days to average vitals (1-7)")] = 7,
    latest_window_hours: Annotated[
        int, Query(ge=1, le=24, description="Hours for latest readings to be considered valid (1-24)")
    ] = 4,
) -> BodySummary | None:
    """Returns comprehensive body metrics with semantic grouping.

    Response is organized into three categories:
    - **static**: Slow-changing values (weight, height, body fat, muscle mass, BMI, age)
      Returns the most recent recorded value for each field.
    - **averaged**: Vitals averaged over a period (resting HR, HRV)
      Period is configurable via `average_period` parameter (1-7 days).
    - **latest**: Point-in-time readings (body temperature, blood pressure)
      Only returned if measured within `latest_window_hours` (default 4 hours).

    Returns null if no body data exists for the user.
    """
    return await summaries_service.get_body_summary(db, user_id, average_period, latest_window_hours)
