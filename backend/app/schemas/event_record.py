from datetime import datetime
from decimal import Decimal
from typing import Literal, TypedDict
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import BaseQueryParams


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
    device_id: str | None = Field(
        None,
        description="Optional device identifier used to resolve the external mapping",
    )

    duration_seconds: int | None = None
    start_datetime: datetime
    end_datetime: datetime


class EventRecordCreate(EventRecordBase):
    """Schema for creating an event record entry."""

    id: UUID
    external_id: str | None = Field(
        None,
        description="Provider-specific record identifier (e.g., Suunto workoutId) for deduplication.",
    )
    provider_name: str | None = Field(
        None,
        description="Provider name (e.g., 'suunto', 'garmin') for external mapping.",
    )
    user_id: UUID
    external_device_mapping_id: UUID | None = Field(
        None,
        description="Existing mapping identifier if the caller has already created one.",
    )


class EventRecordUpdate(EventRecordBase):
    """Schema for updating an event record."""


class EventRecordResponse(EventRecordBase):
    """Schema returned to API consumers."""

    id: UUID
    external_id: str | None
    user_id: UUID | None
    provider_name: str | None
    external_device_mapping_id: UUID | None


class EventRecordQueryParams(BaseQueryParams):
    """Filtering and sorting parameters for event records."""

    cursor: str | None = Field(None, description="Pagination cursor")
    limit: int = Field(50, ge=1, le=1000, description="Maximum number of records to return")
    category: str | None = Field(
        "workout",
        description="Record category (workout, sleep, etc). Defaults to workout.",
    )
    start_datetime: datetime | None = Field(None, description="Start datetime for filtering records")
    end_datetime: datetime | None = Field(None, description="End datetime for filtering records")
    record_type: str | None = Field(None, description="Subtype filter (e.g. HKWorkoutActivityTypeRunning)")
    device_id: str | None = Field(None, description="Filter by originating device id")
    source_name: str | None = Field(None, description="Filter by source/app name")
    provider_name: str | None = Field(None, description="Filter by provider name")
    external_device_mapping_id: UUID | None = Field(None, description="Filter by device mapping identifier")
    min_duration: int | None = Field(None, description="Minimum duration in seconds")
    max_duration: int | None = Field(None, description="Maximum duration in seconds")
    sort_by: (
        Literal[
            "start_datetime",
            "end_datetime",
            "duration_seconds",
            "type",
            "source_name",
        ]
        | None
    ) = Field(
        "start_datetime",
        description="Sort field",
    )
