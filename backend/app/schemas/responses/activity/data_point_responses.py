from datetime import date, datetime
from typing import TypedDict

from app.schemas.common_types import SourceMetadata
from app.schemas.series_types import SeriesType
from pydantic import BaseModel


class TimeSeriesSample(BaseModel):
    timestamp: datetime
    type: SeriesType
    value: float | int
    unit: str
    source: SourceMetadata | None = None


class ActivityAggregateResult(TypedDict):
    """Result from daily activity aggregation query."""

    activity_date: date
    source: str | None
    device_model: str | None
    steps_sum: int
    active_energy_sum: float
    basal_energy_sum: float
    hr_avg: int | None
    hr_max: int | None
    hr_min: int | None
    distance_sum: float | None
    flights_climbed_sum: int | None


class ActiveMinutesResult(TypedDict):
    """Result from daily active/sedentary minutes query."""

    activity_date: date
    source: str | None
    device_model: str | None
    active_minutes: int
    tracked_minutes: int
    sedentary_minutes: int


class IntensityMinutesResult(TypedDict):
    """Result from daily intensity minutes query."""

    activity_date: date
    source: str | None
    device_model: str | None
    light_minutes: int
    moderate_minutes: int
    vigorous_minutes: int
