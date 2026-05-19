from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.database import DbSession
from app.schemas.responses.activity import (
    ActivitySummary,
    BodyDailySummary,
    BodySummary,
    RecoverySummary,
    SleepSummary,
)
from app.schemas.responses.dashboard import UserDataSummaryResponse
from app.schemas.utils import PaginatedResponse
from app.services import ApiKeyDep, system_info_service
from app.services.summaries_service import summaries_service
from app.utils.dates import parse_query_datetime

router = APIRouter()


@router.get("/users/{user_id}/summaries/activity")
def get_activity_summary(
    user_id: UUID,
    start_date: str,
    end_date: str,
    db: DbSession,
    _api_key: ApiKeyDep,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=400)] = 50,
    sort_order: Annotated[str, Query(pattern="^(asc|desc)$")] = "asc",
) -> PaginatedResponse[ActivitySummary]:
    """Returns daily aggregated activity metrics.

    Aggregates time-series data (steps, energy, heart rate, etc.) by day.
    """
    start_datetime = parse_query_datetime(start_date)
    end_datetime = parse_query_datetime(end_date)
    return summaries_service.get_activity_summaries(
        db, user_id, start_datetime, end_datetime, cursor, limit, sort_order
    )


@router.get("/users/{user_id}/summaries/sleep")
def get_sleep_summary(
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
    return summaries_service.get_sleep_summaries(db, user_id, start_datetime, end_datetime, cursor, limit)


@router.get("/users/{user_id}/summaries/recovery")
def get_recovery_summary(
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
def get_body_summary(
    user_id: UUID,
    db: DbSession,
    _api_key: ApiKeyDep,
    average_period: Annotated[int, Query(ge=1, le=7, description="Days to average vitals (1-7)")] = 7,
) -> BodySummary | None:
    """Returns comprehensive body metrics with semantic grouping.

    Response is organized into three categories:
    - **slow_changing**: Slow-changing values (weight, height, body fat, muscle mass, BMI, age)
      Returns the most recent recorded value for each field.
    - **averaged**: Vitals averaged over a period (resting HR, HRV)
      Period is configurable via `average_period` parameter (1-7 days).
    - **latest**: Most recent point-in-time readings (body temperature, blood pressure)
      Each value is returned with its measurement timestamp so callers can decide how to
      surface freshness.

    Returns null if no body data exists for the user.
    """
    return summaries_service.get_body_summary(db, user_id, average_period)


@router.get("/users/{user_id}/summaries/body/daily")
def get_body_summary_daily(
    user_id: UUID,
    start_date: str,
    end_date: str,
    db: DbSession,
    _api_key: ApiKeyDep,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=400)] = 50,
    sort_order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
) -> PaginatedResponse[BodyDailySummary]:
    """Returns paginated per-day body rollups.

    For each (date, source, device) the latest reading of the day is reported for
    each tracked body series (weight, height, body fat, muscle mass, BMI, resting HR,
    HRV, body/skin temperature, blood pressure). Days with no readings are omitted.
    """
    start_datetime = parse_query_datetime(start_date)
    end_datetime = parse_query_datetime(end_date)
    return summaries_service.get_body_summaries_daily(
        db, user_id, start_datetime, end_datetime, cursor, limit, sort_order
    )


@router.get("/users/{user_id}/summaries/data")
def get_data_summary(
    user_id: UUID,
    db: DbSession,
    _api_key: ApiKeyDep,
) -> UserDataSummaryResponse:
    """Returns per-user data counts grouped by series type, event type, and provider."""
    return system_info_service.get_user_data_summary(db, user_id)
