from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict


class DailyHrvScore(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    hrv_value_ms: float | None
    has_data: bool


class HrvCvScoreResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    hrv_cv: float | None
    metric_type: Literal["RMSSD", "SDNN"] | None
    days_counted: int
    lookback_days: int
    daily_scores: list[DailyHrvScore]
