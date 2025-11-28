from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from app.schemas.common import BaseQueryParams


class WorkoutStatisticCreate(BaseModel):
    """Schema for creating a workout statistic."""

    id: UUID
    user_id: UUID
    workout_id: UUID | None = None

    type: str

    start_datetime: datetime
    end_datetime: datetime
    min: float | int | None = None
    max: float | int | None = None
    avg: float | int | None = None
    unit: str


class WorkoutStatisticUpdate(BaseModel):
    """Schema for updating a workout statistic."""

    type: str | None = None
    start_datetime: datetime | None = None
    end_datetime: datetime | None = None
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
    start_datetime: datetime
    end_datetime: datetime
    min: float | int | None = None
    max: float | int | None = None
    avg: float | int | None = None
    unit: str
