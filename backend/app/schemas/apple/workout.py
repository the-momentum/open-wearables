from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field
from typing import Literal

from app.schemas.apple.common import BaseQueryParams
from app.schemas.apple.workout_statistics import WorkoutStatisticResponse


class WorkoutCreate(BaseModel):
    """Schema for creating a workout."""
    
    id: UUID
    provider_id: UUID | None = None
    user_id: UUID

    type: str | None = None

    duration: Decimal
    durationUnit: str
    sourceName: str

    startDate: datetime
    endDate: datetime
    
class WorkoutUpdate(BaseModel):
    """Schema for updating a workout."""

    type: str | None = None
    
    duration: Decimal | None = None
    durationUnit: str | None = None
    sourceName: str | None = None
    
    startDate: datetime | None = None
    endDate: datetime | None = None
    
class WorkoutResponse(BaseModel):
    """Schema for a workout response."""

    id: UUID

    type: str | None = None
    
    duration: Decimal
    durationUnit: str
    sourceName: str
    
    startDate: datetime
    endDate: datetime
    
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
    duration_unit: str | None = Field(None, description="Duration unit (e.g., 'min', 'hr', 'sec')")
    sort_by: Literal["startDate", "endDate", "duration", "type", "sourceName"] | None = Field(
        "startDate",
        description="Sort field",
    )
