from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.database import DbSession
from app.schemas.responses.activity import (
    ActivitySummary,
    BodySummary,
    RecoverySummary,
    SleepSummary,
)
from app.schemas.utils import PaginatedResponse
from app.services import ApiKeyDep
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
    """Returns daily recovery scores combining HRV, resting heart rate, and sleep.

    Recovery score (0-100) is computed per day using a z-score framework:
    - HRV SDNN (40%): nervous system stress vs personal baseline
    - Resting HR (30%): cardiovascular load vs personal baseline
    - Sleep efficiency (30%): provider-reported sleep quality

    Missing metrics are handled by redistributing their weight proportionally.
    A score is omitted when both HRV and RHR are unavailable for a given day.

    Baselines are built from up to 28 days of prior history.
    """
    start_datetime = parse_query_datetime(start_date)
    end_datetime = parse_query_datetime(end_date)
    return summaries_service.get_recovery_summaries(db, user_id, start_datetime, end_datetime, cursor, limit)


@router.get("/users/{user_id}/summaries/body")
def get_body_summary(
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
    return summaries_service.get_body_summary(db, user_id, average_period, latest_window_hours)
