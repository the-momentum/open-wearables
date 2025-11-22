from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class WorkoutBase(BaseModel):
    """Base schema for Workout."""

    provider_id: UUID | None = None
    type: str | None = None
    duration: float
    durationUnit: str
    sourceName: str
    startDate: datetime
    endDate: datetime


class WorkoutCreate(WorkoutBase):
    """Schema for creating a new Workout."""

    user_id: UUID


class WorkoutUpdate(BaseModel):
    """Schema for updating Workout."""

    type: str | None = None
    duration: float | None = None
    durationUnit: str | None = None
    sourceName: str | None = None
    startDate: datetime | None = None
    endDate: datetime | None = None


class WorkoutRead(WorkoutBase):
    """Schema for reading Workout."""

    id: UUID
    user_id: UUID

    class Config:
        from_attributes = True
