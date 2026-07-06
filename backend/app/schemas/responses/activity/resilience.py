from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict


class DailyHrvScore(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    hrv_value_ms: float | None
    has_data: bool


class HrvCvScoreResult(BaseModel):
    """Result of an HRV-CV resilience calculation.

    ``hrv_cv`` is the raw coefficient of variation (std/mean of daily HRV
    averages), expressed as a fraction — e.g. 0.123 means 12.3 %.  It is
    stored in the DB as NUMERIC(6,3) and displayed on the UI as X.X %.

    ``resilience_score`` is the same value mapped to a 0–100 scale via a
    linear drop: CV ≤ 7 % → 100, CV ≥ 40 % → 0, linear between.
    Analogous to sleep/recovery scores.  None when ``hrv_cv`` is None
    (insufficient data).
    """

    model_config = ConfigDict(from_attributes=True)

    hrv_cv: float | None
    resilience_score: int | None
    metric_type: Literal["RMSSD", "SDNN"] | None
    days_counted: int
    lookback_days: int
    daily_scores: list[DailyHrvScore]
