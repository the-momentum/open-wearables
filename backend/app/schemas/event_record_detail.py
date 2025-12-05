from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class EventRecordDetailBase(BaseModel):
    """Base schema for event record detail."""

    heart_rate_min: Decimal | None = None
    heart_rate_max: Decimal | None = None
    heart_rate_avg: Decimal | None = None

    steps_min: Decimal | None = None
    steps_max: Decimal | None = None
    steps_avg: Decimal | None = None
    steps_total: Decimal | None = None

    max_speed: Decimal | None = None
    max_watts: Decimal | None = None

    average_speed: Decimal | None = None
    average_watts: Decimal | None = None

    moving_time_seconds: Decimal | None = None
    total_elevation_gain: Decimal | None = None

    elev_high: Decimal | None = None
    elev_low: Decimal | None = None

    sleep_total_duration_minutes: Decimal | None = None
    sleep_time_in_bed_minutes: Decimal | None = None
    sleep_efficiency_score: Decimal | None = None
    sleep_deep_minutes: Decimal | None = None
    sleep_rem_minutes: Decimal | None = None
    sleep_light_minutes: Decimal | None = None
    sleep_awake_minutes: Decimal | None = None


class EventRecordDetailCreate(EventRecordDetailBase):
    """Schema for creating an event record detail entry."""

    record_id: UUID


class EventRecordDetailUpdate(EventRecordDetailBase):
    """Schema for updating an event record detail entry."""


class EventRecordDetailResponse(EventRecordDetailBase):
    """Schema returned to API consumers."""

    record_id: UUID
