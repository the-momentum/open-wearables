from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.enums import Resolution, SeriesType
from app.utils.dates import ZoneOffset
from app.utils.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

from .source_filters import SourceFilterParams


class TimeSeriesSampleBase(BaseModel):
    user_id: UUID
    source: str | None = None  # e.g., "apple_health_sdk", "garmin_connect_api"
    device_model: str | None = None  # e.g., "iPhone10,5", "Forerunner 910XT"
    data_source_id: UUID | None = Field(
        None,
        description="Existing data source identifier if already created upstream.",
    )
    recorded_at: datetime
    zone_offset: ZoneOffset = None
    value: Decimal | float | int
    series_type: SeriesType
    # True = daily total. False/None = not a daily total (summable sample); aggregation
    # treats None as False. Set explicitly by the provider save path (Garmin dailies vs epochs).
    is_daily_total: bool | None = None


class TimeSeriesSampleCreate(TimeSeriesSampleBase):
    id: UUID
    external_id: str | None = None
    provider: str | None = None
    user_connection_id: UUID | None = None
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


class TimeSeriesQueryParams(SourceFilterParams):
    """Filters for retrieving time series samples."""

    start_datetime: datetime | None = Field(None, description="Lower bound (inclusive) for recorded timestamp")
    end_datetime: datetime | None = Field(None, description="Upper bound (inclusive) for recorded timestamp")
    limit: int = Field(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Maximum number of samples to return")
    cursor: str | None = Field(
        None,
        description="Pagination cursor (use next_cursor for forward, previous_cursor for backward)",
    )
    resolution: Resolution = Resolution.RAW
