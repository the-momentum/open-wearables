from datetime import date, datetime
from typing import TypedDict

from pydantic import BaseModel

from app.schemas.enums import SeriesType
from app.schemas.utils import SourceMetadata
from app.utils.dates import ZoneOffset


class TimeSeriesSample(BaseModel):
    timestamp: datetime
    zone_offset: ZoneOffset = None
    type: SeriesType
    value: float | int
    unit: str
    source: SourceMetadata | None = None
    # True = daily total. False/None = not a daily total (summable sample); None is a
    # legacy row and is treated as False by the aggregation.
    is_daily_total: bool | None = None


class ActivityAggregateResult(TypedDict):
    """Result from daily activity aggregation query."""

    activity_date: date
    provider: str | None
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
    active_time_minutes: int | None  # Provider-reported daily active time; None when not reported


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
