from uuid import UUID
from pydantic import BaseModel, ConfigDict

class WorkoutStatisticBase(BaseModel):
    """Base schema for workout statistics."""
    type: str
    value: float | int
    unit: str


# Input schemas
class WorkoutStatisticJSON(WorkoutStatisticBase):
    """Schema for parsing WorkoutStatistic from JSON import."""


class WorkoutStatisticCreate(WorkoutStatisticBase):
    """Schema for creating a WorkoutStatistic."""
    user_id: UUID
    workout_id: UUID


class WorkoutStatisticUpdate(WorkoutStatisticBase):
    """Schema for creating a WorkoutStatistic."""
    id: int
    user_id: UUID
    workout_id: UUID


# Output schema
class WorkoutStatisticResponse(WorkoutStatisticBase):
    """Schema for WorkoutStatistic response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: UUID
    workout_id: UUID


class WorkoutStatisticIn(WorkoutStatisticBase):
    """Schema for workout statistics from JSON input."""
    model_config = ConfigDict(from_attributes=True)
