from typing import Annotated, Literal, Union
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.database import DbSession
from app.schemas.common_types import PaginatedResponse
from app.schemas.timeseries import (
    BiometricType,
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
    type: BiometricType,
    start_time: str,
    end_time: str,
    db: DbSession,
    _api_key: ApiKeyDep,
    resolution: Literal["raw", "1min", "5min", "15min", "1hour"] = "raw",
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> PaginatedResponse[Union[HeartRateSample, HrvSample, Spo2Sample, BloodGlucoseSample]]:
    """Returns granular biometric measurements (HR, HRV, SpO2, Glucose, etc.)."""
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/users/{user_id}/timeseries/activity")
async def get_activity_timeseries(
    user_id: UUID,
    start_time: str,
    end_time: str,
    db: DbSession,
    _api_key: ApiKeyDep,
    resolution: Literal["raw", "1min", "5min", "15min", "1hour"] = "raw",
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> PaginatedResponse[StepsSample]:
    """Returns granular activity data (steps, cadence, etc.)."""
    raise HTTPException(status_code=501, detail="Not implemented")
