from datetime import datetime
from decimal import Decimal
from typing import Literal, TypedDict
from uuid import UUID
from enum import StrEnum

from pydantic import BaseModel, Field

from app.schemas.common import BaseQueryParams


class WorkoutType(StrEnum):
    RUNNING = "running"
    WALKING = "walking"
    CYCLING = "cycling"
    SWIMMING = "swimming"
    OTHER = "other"


class EventRecordMetrics(TypedDict, total=False):
    """Optional workout or sleep metrics collected from providers."""

    heart_rate_min: Decimal | None
    heart_rate_max: Decimal | None
    heart_rate_avg: Decimal | None
    steps_min: Decimal | None
    steps_max: Decimal | None
    steps_avg: Decimal | None
    steps_total: Decimal | None
    max_speed: Decimal | None
    max_watts: Decimal | None
    moving_time_seconds: Decimal | None
    total_elevation_gain: Decimal | None
    average_speed: Decimal | None
    average_watts: Decimal | None
    elev_high: Decimal | None
    elev_low: Decimal | None
    sleep_total_duration_minutes: Decimal | None
    sleep_time_in_bed_minutes: Decimal | None
    sleep_efficiency_score: Decimal | None
    sleep_deep_minutes: Decimal | None
    sleep_rem_minutes: Decimal | None
    sleep_light_minutes: Decimal | None
    sleep_awake_minutes: Decimal | None


class EventRecordBase(BaseModel):
    """Base schema for event record."""

    category: str = Field("workout", description="High-level category such as workout or sleep")
    type: str | None = Field(None, description="Provider-specific subtype, e.g. running")

    source_name: str = Field(description="Source/app name")
    device_id: str | None = Field(
        None,
        description="Optional device identifier used to resolve the external mapping",
    )

    duration_seconds: Decimal | None = None
    start_datetime: datetime
    end_datetime: datetime


class EventRecordCreate(EventRecordBase):
    """Schema for creating an event record entry."""

    id: UUID
    provider_id: str | None = None
    user_id: UUID
    external_mapping_id: UUID | None = Field(
        None,
        description="Existing mapping identifier if the caller has already created one.",
    )


class EventRecordUpdate(EventRecordBase):
    """Schema for updating an event record."""


class EventRecordResponse(EventRecordBase):
    """Schema returned to API consumers."""

    id: UUID
    user_id: UUID
    provider_id: str | None
    external_mapping_id: UUID


class EventRecordQueryParams(BaseQueryParams):
    """Filtering and sorting parameters for event records."""

    category: str | None = Field(
        "workout",
        description="Record category (workout, sleep, etc). Defaults to workout.",
    )
    record_type: str | None = Field(None, description="Subtype filter (e.g. HKWorkoutActivityTypeRunning)")
    device_id: str | None = Field(None, description="Filter by originating device id")
    source_name: str | None = Field(None, description="Filter by source/app name")
    provider_id: str | None = Field(None, description="Filter by provider identifier")
    external_mapping_id: UUID | None = Field(None, description="Filter by mapping identifier")
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
