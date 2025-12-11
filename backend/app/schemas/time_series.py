from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class SeriesType(str, Enum):
    steps = "steps"
    heart_rate = "heart_rate"
    energy = "energy"
    height = "height"
    weight = "weight"
    body_fat_percentage = "body_fat_percentage"
    resting_heart_rate = "resting_heart_rate"
    body_temperature = "body_temperature"
    distance_walking_running = "distance_walking_running"
    distance_cycling = "distance_cycling"
    respiratory_rate = "respiratory_rate"
    walking_heart_rate_average = "walking_heart_rate_average"
    heart_rate_variability_sdnn = "heart_rate_variability_sdnn"
    oxygen_saturation = "oxygen_saturation"


class TimeSeriesSampleBase(BaseModel):
    user_id: UUID
    provider_name: str
    device_id: str | None = None
    external_device_mapping_id: UUID | None = Field(
        None,
        description="Existing mapping identifier if already created upstream.",
    )
    recorded_at: datetime
    value: Decimal | float | int
    series_type: SeriesType


class TimeSeriesSampleCreate(TimeSeriesSampleBase):
    """Generic create payload for data point series."""

    id: UUID


class TimeSeriesSampleUpdate(TimeSeriesSampleBase):
    """Generic update payload for data point series."""


class TimeSeriesSampleResponse(TimeSeriesSampleBase):
    """Generic response payload for data point series."""

    id: UUID
    external_device_mapping_id: UUID


class HeartRateSampleCreate(TimeSeriesSampleCreate):
    """Create payload for heart rate samples."""

    series_type: Literal[SeriesType.heart_rate] = SeriesType.heart_rate


class HeartRateSampleResponse(TimeSeriesSampleResponse):
    """Response payload for heart rate samples."""

    series_type: Literal[SeriesType.heart_rate] = SeriesType.heart_rate


class StepSampleCreate(TimeSeriesSampleCreate):
    """Create payload for step count samples."""

    series_type: Literal[SeriesType.steps] = SeriesType.steps


class StepSampleResponse(TimeSeriesSampleResponse):
    """Response payload for step count samples."""

    series_type: Literal[SeriesType.steps] = SeriesType.steps


class TimeSeriesQueryParams(BaseModel):
    """Filters for retrieving time series samples."""

    start_datetime: datetime | None = Field(None, description="Lower bound (inclusive) for recorded timestamp")
    end_datetime: datetime | None = Field(None, description="Upper bound (inclusive) for recorded timestamp")
    device_id: str | None = Field(
        None,
        description="Device identifier filter; required to retrieve samples",
    )
    provider_name: str | None = Field(None, description="Optional provider name filter")
    external_device_mapping_id: UUID | None = Field(
        None,
        description="Direct mapping identifier filter (skips device lookup).",
    )
