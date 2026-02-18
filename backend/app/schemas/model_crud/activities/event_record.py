from datetime import datetime
from decimal import Decimal
from typing import Literal, TypedDict
from uuid import UUID

from pydantic import BaseModel, Field


class EventRecordMetrics(TypedDict, total=False):
    """Optional workout or sleep metrics collected from providers."""

    heart_rate_min: int | None
    heart_rate_max: int | None
    heart_rate_avg: Decimal | None
    steps_count: int | None
    energy_burned: Decimal | None
    distance: Decimal | None
    max_speed: Decimal | None
    max_watts: Decimal | None
    moving_time_seconds: int | None
    total_elevation_gain: Decimal | None
    average_speed: Decimal | None
    average_watts: Decimal | None
    elev_high: Decimal | None
    elev_low: Decimal | None
    sleep_total_duration_minutes: int | None
    sleep_time_in_bed_minutes: int | None
    sleep_efficiency_score: Decimal | None
    sleep_deep_minutes: int | None
    sleep_rem_minutes: int | None
    sleep_light_minutes: int | None
    sleep_awake_minutes: int | None


class EventRecordBase(BaseModel):
    """Base schema for event record."""

    category: str = Field("workout", description="High-level category such as workout or sleep")
    type: str | None = Field(None, description="Provider-specific subtype, e.g. running")

    source_name: str = Field(description="Source/app name")
    device_model: str | None = Field(
        None,
        description="Device model/name for data source tracking",
    )

    duration_seconds: int | None = None
    start_datetime: datetime
    end_datetime: datetime


class EventRecordCreate(EventRecordBase):
    id: UUID
    external_id: str | None = None
    source: str | None = None
    user_id: UUID
    provider: str | None = None
    user_connection_id: UUID | None = None
    data_source_id: UUID | None = None
    software_version: str | None = None


class EventRecordUpdate(EventRecordBase):
    """Schema for updating an event record."""


class EventRecordResponse(EventRecordBase):
    """Schema returned to API consumers."""

    id: UUID
    external_id: str | None
    user_id: UUID | None
    source: str | None
    data_source_id: UUID | None


class EventRecordQueryParams(BaseModel):
    """Filtering and sorting parameters for event records."""

    # Pagination
    cursor: str | None = Field(None, description="Pagination cursor")
    limit: int = Field(50, ge=1, le=1000, description="Maximum number of records to return")
    offset: int = Field(0, ge=0, description="Number of results to skip (for non-cursor pagination)")

    # Date filtering
    start_datetime: datetime | None = Field(None, description="Start datetime for filtering records")
    end_datetime: datetime | None = Field(None, description="End datetime for filtering records")

    # Category and type filtering
    category: str | None = Field(
        "workout",
        description="Record category (workout, sleep, etc). Defaults to workout.",
    )
    record_type: str | None = Field(None, description="Subtype filter (e.g. HKWorkoutActivityTypeRunning)")

    # Source filtering
    device_model: str | None = Field(None, description="Filter by device model")
    source_name: str | None = Field(None, description="Filter by source/app name")
    source: str | None = Field(None, description="Filter by data source")
    data_source_id: UUID | None = Field(None, description="Filter by data source identifier")

    # Duration filtering
    min_duration: int | None = Field(None, description="Minimum duration in seconds")
    max_duration: int | None = Field(None, description="Maximum duration in seconds")

    # Sorting
    sort_by: Literal[
        "start_datetime",
        "end_datetime",
        "duration_seconds",
        "type",
        "source_name",
    ] = Field("start_datetime", description="Sort field")
    sort_order: Literal["asc", "desc"] = Field("desc", description="Sort order")
