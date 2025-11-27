from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class WorkoutStatisticCreate(BaseModel):
    """Schema for creating a workout statistic."""

    id: UUID
    user_id: UUID
    workout_id: UUID | None = None

    type: str
    sourceName: str

    startDate: datetime
    endDate: datetime
    min: float | int | None = None
    max: float | int | None = None
    avg: float | int | None = None
    unit: str


class WorkoutStatisticUpdate(BaseModel):
    """Schema for updating a workout statistic."""

    type: str | None = None
    sourceName: str | None = None
    startDate: datetime | None = None
    endDate: datetime | None = None
    min: float | int | None = None
    max: float | int | None = None
    avg: float | int | None = None
    unit: str | None = None


class WorkoutStatisticResponse(BaseModel):
    """Schema for a workout statistic response."""

    id: UUID
    user_id: UUID
    workout_id: UUID

    type: str
    sourceName: str
    startDate: datetime
    endDate: datetime
    min: float | int | None = None
    max: float | int | None = None
    avg: float | int | None = None
    unit: str


# class WorkoutStatisticBase(BaseModel):
#     """Base schema for workout statistics."""

#     type: str
#     value: float | int
#     unit: str


# # Input schemas
# class WorkoutStatisticJSON(WorkoutStatisticBase):
#     """Schema for parsing WorkoutStatistic from JSON import."""


# class WorkoutStatisticCreate(WorkoutStatisticBase):
#     """Schema for creating a WorkoutStatistic."""

#     id: UUID
#     user_id: UUID
#     workout_id: UUID


# class WorkoutStatisticUpdate(WorkoutStatisticBase):
#     """Schema for creating a WorkoutStatistic."""

#     id: UUID
#     user_id: UUID
#     workout_id: UUID


# # Output schema
# class WorkoutStatisticResponse(WorkoutStatisticBase):
#     """Schema for WorkoutStatistic response."""

#     model_config = ConfigDict(from_attributes=True)

#     id: UUID
#     user_id: UUID
#     workout_id: UUID


# class WorkoutStatisticIn(WorkoutStatisticBase):
#     """Schema for workout statistics from JSON input."""

#     model_config = ConfigDict(from_attributes=True)
