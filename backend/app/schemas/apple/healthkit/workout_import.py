# ruff: noqa: N815

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.constants.workout_types.apple_sdk import SDK_TO_UNIFIED

from .source_info import SourceInfo

# Extract all valid SDK workout type keys for Literal type
# This ensures type safety and OpenAPI documentation
_SDK_WORKOUT_TYPE_KEYS = tuple(SDK_TO_UNIFIED.keys())
SDKWorkoutType = Literal[_SDK_WORKOUT_TYPE_KEYS]  # type: ignore[valid-type]


class WorkoutStatisticJSON(BaseModel):
    type: str
    unit: str
    value: float | int


class WorkoutJSON(BaseModel):
    uuid: str | None = None
    user_id: str | None = None
    type: SDKWorkoutType | None = None
    startDate: datetime
    endDate: datetime
    source: SourceInfo | None = None
    workoutStatistics: list[WorkoutStatisticJSON] | None = None
