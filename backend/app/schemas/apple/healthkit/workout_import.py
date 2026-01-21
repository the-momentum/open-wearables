# ruff: noqa: N815

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from .source_info import SourceInfo


class WorkoutJSON(BaseModel):
    uuid: str | None = None
    user_id: str | None = None
    type: str | None = None
    startDate: datetime
    endDate: datetime
    sourceName: str | None = None
    source: SourceInfo | None = None
    workoutStatistics: list[WorkoutStatisticJSON] | None = None


class WorkoutStatisticJSON(BaseModel):
    type: str
    unit: str
    value: float | int
