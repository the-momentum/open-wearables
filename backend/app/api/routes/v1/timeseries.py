from datetime import datetime
from typing import Annotated, Literal, Union
from uuid import UUID

from fastapi import APIRouter, Query

from app.database import DbSession
from app.schemas import TimeSeriesQueryParams
from app.schemas.taxonomy_common import Pagination, TimeseriesMetadata
from app.schemas.taxonomy_timeseries import (
    BiometricType,
    BloodGlucoseSample,
    HeartRateSample,
    HrvSample,
    Spo2Sample,
    StepsSample,
)
from app.services import ApiKeyDep, time_series_service

router = APIRouter()


@router.get("/users/{user_id}/timeseries/biometrics")
async def get_biometrics_timeseries(
    user_id: UUID,
    type: BiometricType,
    start_time: datetime,
    end_time: datetime,
    db: DbSession,
    _api_key: ApiKeyDep,
    resolution: Literal["raw", "1min", "5min", "15min", "1hour"] = "raw",
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[
    str,
    list[Union[HeartRateSample, HrvSample, Spo2Sample, BloodGlucoseSample]]  # Using Union for documentation
    | TimeseriesMetadata
    | Pagination,
]:
    """Returns granular biometric measurements (HR, HRV, SpO2, Glucose, etc.)."""
    params = TimeSeriesQueryParams(
        start_datetime=start_time,
        end_datetime=end_time,
    )
    return await time_series_service.get_biometrics_series(db, user_id, type, params)


@router.get("/users/{user_id}/timeseries/activity")
async def get_activity_timeseries(
    user_id: UUID,
    start_time: datetime,
    end_time: datetime,
    db: DbSession,
    _api_key: ApiKeyDep,
    resolution: Literal["raw", "1min", "5min", "15min", "1hour"] = "raw",
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, list[StepsSample] | TimeseriesMetadata | Pagination]:
    """Returns granular activity data (steps, cadence, etc.)."""
    params = TimeSeriesQueryParams(
        start_datetime=start_time,
        end_datetime=end_time,
    )
    return await time_series_service.get_activity_series(db, user_id, params)
