from typing import Annotated, Literal, Union
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.database import DbSession
from app.schemas.common_types import PaginatedResponse
from app.schemas.series_types import SeriesType, is_activity_type, is_biometric_type
from app.schemas.timeseries_samples import (
    BloodGlucoseSample,
    HeartRateSample,
    HrvSample,
    Spo2Sample,
    StepsSample,
)
from app.services import ApiKeyDep

router = APIRouter()


@router.get("/users/{user_id}/timeseries/biometrics")
async def get_biometrics_timeseries(
    user_id: UUID,
    type: SeriesType,
    start_time: str,
    end_time: str,
    db: DbSession,
    _api_key: ApiKeyDep,
    resolution: Literal["raw", "1min", "5min", "15min", "1hour"] = "raw",
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> PaginatedResponse[Union[HeartRateSample, HrvSample, Spo2Sample, BloodGlucoseSample]]:
    """Returns granular biometric measurements (HR, HRV, SpO2, Glucose, etc.)."""
    if not is_biometric_type(type):
        raise HTTPException(status_code=400, detail=f"Type '{type}' is not a biometric metric")
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/users/{user_id}/timeseries/activity")
async def get_activity_timeseries(
    user_id: UUID,
    type: SeriesType,
    start_time: str,
    end_time: str,
    db: DbSession,
    _api_key: ApiKeyDep,
    resolution: Literal["raw", "1min", "5min", "15min", "1hour"] = "raw",
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> PaginatedResponse[StepsSample]:
    """Returns granular activity data (steps, cadence, etc.)."""
    if not is_activity_type(type):
        raise HTTPException(status_code=400, detail=f"Type '{type}' is not an activity metric")
    raise HTTPException(status_code=501, detail="Not implemented")
