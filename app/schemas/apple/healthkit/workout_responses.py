from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.apple.common import DateRange


class WorkoutSummary(BaseModel):
    """HealthKit workout summary with statistics."""

    total_statistics: int
    avg_statistic_value: float
    max_statistic_value: float
    min_statistic_value: float
    avg_heart_rate: float
    max_heart_rate: float
    min_heart_rate: float
    total_calories: float


class WorkoutResponse(BaseModel):
    """Individual HealthKit workout response model - matches unified database model."""

    id: UUID
    type: str | None = None
    startDate: datetime
    endDate: datetime
    duration: float
    durationUnit: str
    sourceName: str | None = None
    user_id: UUID
    summary: WorkoutSummary


class WorkoutMeta(BaseModel):
    """Metadata for HealthKit workout response."""

    requested_at: str  # ISO 8601
    filters: dict
    result_count: int
    total_count: int
    date_range: DateRange


class WorkoutListResponse(BaseModel):
    """Response model for HealthKit workout list endpoint."""

    data: list[WorkoutResponse]
    meta: WorkoutMeta