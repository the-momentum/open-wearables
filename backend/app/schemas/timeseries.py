from datetime import date, datetime
from decimal import Decimal
from typing import Literal, TypedDict
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common_types import SourceMetadata
from app.schemas.series_types import SeriesType

# --- API Response Models (Unified) ---


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


# --- Internal / CRUD Models ---


class TimeSeriesSampleBase(BaseModel):
    user_id: UUID
    source: str | None = None  # e.g., "apple_health_sdk", "garmin_connect_api"
    device_model: str | None = None  # e.g., "iPhone10,5", "Forerunner 910XT"
    data_source_id: UUID | None = Field(
        None,
        description="Existing data source identifier if already created upstream.",
    )
    recorded_at: datetime
    value: Decimal | float | int
    series_type: SeriesType


class TimeSeriesSampleCreate(TimeSeriesSampleBase):
    """Generic create payload for data point series."""

    id: UUID
    external_id: str | None = None
    manufacturer: str | None = None
    software_version: str | None = None


class TimeSeriesSampleUpdate(TimeSeriesSampleBase):
    """Generic update payload for data point series."""


class TimeSeriesSampleResponse(TimeSeriesSampleBase):
    """Generic response payload for data point series."""

    id: UUID
    data_source_id: UUID


class HeartRateSampleCreate(TimeSeriesSampleCreate):
    """Create payload for heart rate samples."""

    series_type: Literal[SeriesType.heart_rate] = SeriesType.heart_rate


class StepSampleCreate(TimeSeriesSampleCreate):
    """Create payload for step count samples."""

    series_type: Literal[SeriesType.steps] = SeriesType.steps


class TimeSeriesQueryParams(BaseModel):
    """Filters for retrieving time series samples."""

    start_datetime: datetime | None = Field(None, description="Lower bound (inclusive) for recorded timestamp")
    end_datetime: datetime | None = Field(None, description="Upper bound (inclusive) for recorded timestamp")
    device_model: str | None = Field(
        None,
        description="Device model filter",
    )
    source: str | None = Field(None, description="Optional data source filter")
    data_source_id: UUID | None = Field(
        None,
        description="Direct data source identifier filter.",
    )
    limit: int = Field(50, ge=1, le=1000, description="Maximum number of samples to return")
    cursor: str | None = Field(
        None,
        description="Pagination cursor (use next_cursor for forward, previous_cursor for backward)",
    )
