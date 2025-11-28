from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import BaseQueryParams
from app.schemas.workout_statistics import WorkoutStatisticResponse


class WorkoutCreate(BaseModel):
    """Schema for creating a workout."""

    id: UUID
    provider_id: str | None = None
    user_id: UUID

    type: str | None = None

    duration_seconds: Decimal
    source_name: str

    start_datetime: datetime
    end_datetime: datetime


class WorkoutUpdate(BaseModel):
    """Schema for updating a workout."""

    type: str | None = None

    duration_seconds: Decimal | None = None
    source_name: str | None = None

    start_datetime: datetime | None = None
    end_datetime: datetime | None = None


class WorkoutResponse(BaseModel):
    """Schema for a workout response."""

    id: UUID

    type: str | None = None

    duration_seconds: Decimal
    source_name: str

    start_datetime: datetime
    end_datetime: datetime

    statistics: list[WorkoutStatisticResponse]


class WorkoutQueryParams(BaseQueryParams):
    """Query parameters for HealthKit workout filtering and pagination."""

    workout_type: str | None = Field(
        None,
        description="Workout type (e.g., 'HKWorkoutActivityTypeRunning', 'HKWorkoutActivityTypeWalking')",
    )
    source_name: str | None = Field(None, description="Source name of the workout (e.g., 'Apple Watch', 'iPhone')")
    min_duration: int | None = Field(None, description="Minimum duration in seconds")
    max_duration: int | None = Field(None, description="Maximum duration in seconds")
    sort_by: Literal["start_datetime", "end_datetime", "duration_seconds", "type", "source_name"] | None = Field(
        "start_datetime", description="Sort field"
    )
