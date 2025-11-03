from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class WorkoutCreate(BaseModel):
    """Schema for creating a workout."""

    id: UUID
    user_id: UUID
    type: str | None = None
    startDate: datetime
    endDate: datetime
    duration: Decimal
    durationUnit: str
    sourceName: str | None = None


class WorkoutUpdate(BaseModel):
    """Schema for updating a workout."""

    type: str | None = None
    startDate: datetime
    endDate: datetime
    sourceName: str | None = None
