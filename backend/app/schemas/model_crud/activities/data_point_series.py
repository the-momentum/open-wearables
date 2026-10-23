from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.constants.devices_map import normalize_device_model
from app.schemas.enums import DeviceType, PeriodKind, Resolution, SeriesType
from app.utils.dates import ZoneOffset, iso_to_timezone
from app.utils.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

from .source_filters import SourceFilterParams


def _offset(zone_offset: object) -> object:
    """Providers spell UTC as "Z", None or "+00:00"; one form, as the sample's ZoneOffset does."""
    return "+00:00" if zone_offset in (None, "Z") else zone_offset


class CalendarPeriod(BaseModel):
    """The calendar period a provider value stands for, with the offset that makes it local."""

    model_config = ConfigDict(frozen=True)

    kind: PeriodKind = PeriodKind.DAY
    start: datetime
    end: datetime
    # A provider day with no offset stays its date, as readers treat a missing offset as UTC.
    zone_offset: str = Field("+00:00", pattern=r"^[+-]\d{2}:\d{2}$")

    _utc_forms = field_validator("zone_offset", mode="before")(_offset)

    @classmethod
    def local_day(cls, start: datetime, seconds: int | None = None, zone_offset: str | None = None) -> Self:
        """A day the provider starts at its own local midnight, given as an instant."""
        return cls(start=start, end=start + timedelta(seconds=seconds or 86400), zone_offset=str(_offset(zone_offset)))

    @classmethod
    def of_date(cls, day: date | str, zone_offset: str | None = None) -> Self:
        """A provider's date (or YYYY-MM-DD): local midnight when the offset is known, UTC midnight otherwise."""
        offset = str(_offset(zone_offset))
        start = datetime.combine(
            date.fromisoformat(day) if isinstance(day, str) else day, time(), iso_to_timezone(offset)
        )
        return cls(start=start, end=start + timedelta(days=1), zone_offset=offset)


StatColumn = Literal["sum", "avg", "min", "max", "last"]


class SessionValue(BaseModel):
    """The event record (a sleep, a workout) a provider value describes."""

    model_config = ConfigDict(frozen=True)

    record_id: UUID
    # None: the column the series type is read from. Set when the provider reports another statistic.
    stat: StatColumn | None = None


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
    window_seconds: int | None = Field(None, gt=0)
    value: Decimal | float | int
    series_type: SeriesType
    # True = daily total. False/None = not a daily total (summable sample); aggregation
    # treats None as False. Set explicitly by the provider save path (Garmin dailies vs epochs).
    is_daily_total: bool | None = None

    _normalize_device_model = field_validator("device_model")(normalize_device_model)


class TimeSeriesSampleCreate(TimeSeriesSampleBase):
    id: UUID
    external_id: str | None = None
    provider: str | None = None
    user_connection_id: UUID | None = None
    software_version: str | None = None
    device_type: DeviceType | None = None
    device_id: str | None = None
    source_app_id: str | None = None
    device_manufacturer: str | None = None
    # Set on a provider's day or session value: it is also written to the matching aggregate table.
    period: CalendarPeriod | None = None
    session: SessionValue | None = None


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
