from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.schemas.apple.auto_export.workout_values import (
    DistanceValue,
    ActiveEnergyValue,
    IntensityValue,
    TemperatureValue,
    HumidityValue,
)


class WorkoutSummary(BaseModel):
    """Workout summary with heart rate and calorie data."""

    avg_heart_rate: float
    max_heart_rate: float
    min_heart_rate: float
    total_calories: float


class WorkoutResponse(BaseModel):
    """Individual workout response model."""

    id: UUID
    name: str
    location: Literal["Indoor", "Outdoor"]
    start: str  # ISO 8601
    end: str  # ISO 8601
    duration: int  # seconds
    distance: DistanceValue
    active_energy_burned: ActiveEnergyValue
    intensity: IntensityValue
    temperature: TemperatureValue | None = None
    humidity: HumidityValue | None = None
    source: str | None = None
    summary: WorkoutSummary


class DateRange(BaseModel):
    """Date range information."""

    start: str
    end: str
    duration_days: int


class WorkoutMeta(BaseModel):
    """Metadata for workout response."""

    requested_at: str  # ISO 8601
    filters: dict
    result_count: int
    date_range: DateRange


class WorkoutListResponse(BaseModel):
    """Response model for workout list endpoint."""

    data: list[WorkoutResponse]
    meta: WorkoutMeta
