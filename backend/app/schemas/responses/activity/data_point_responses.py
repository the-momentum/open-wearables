from datetime import date, datetime
from typing import TypedDict

from pydantic import BaseModel

from app.schemas.enums import ComputedBy, SeriesType
from app.schemas.utils import SourceMetadata
from app.utils.dates import ZoneOffset


class SeriesStats(BaseModel):
    """Every statistic held for a period. The sample's value is the one its series is read by."""

    avg: float | None = None
    min: float | None = None
    max: float | None = None
    sum: float | None = None
    last: float | None = None
    count: int


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
    # Width of a sample reported over a window (a 15-minute epoch is 900); None for an instant.
    window_seconds: int | None = None
    # Day, week and month resolutions: the period's end, who computed it, and all its statistics.
    period_end: datetime | None = None
    computed_by: ComputedBy | None = None
    stats: SeriesStats | None = None


class ActivityAggregateResult(TypedDict):
    """Result from daily activity aggregation query."""

    activity_date: date
    provider: str | None
    source: str | None
    device_model: str | None
    device_type: str | None
    steps_sum: int | None
    active_energy_sum: float | None
    basal_energy_sum: float | None
    total_energy_sum: float | None
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
