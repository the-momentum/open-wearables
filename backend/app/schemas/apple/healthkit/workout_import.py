# ruff: noqa: N815

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.apple.workout_statistics import WorkoutStatisticIn


class WorkoutBase(BaseModel):
    """Base schema for workout."""

    type: str | None = None
    startDate: datetime
    endDate: datetime
    duration: Decimal
    durationUnit: str
    sourceName: str | None = None


class WorkoutJSON(BaseModel):
    uuid: str | None = None
    user_id: str | None = None
    type: str | None = None
    startDate: datetime
    endDate: datetime
    sourceName: str | None = None
    workoutStatistics: list[WorkoutStatisticIn] | None = None


class RootJSON(BaseModel):
    data: dict[str, Any]
