from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.enums import EntrySource, WorkoutIntensity

from .sleep import SleepStage
from .zones import HRZones, PowerZones

# Mirrors the workout_details.label column width (str_255).
LABEL_MAX_LENGTH = 255


class EventRecordDetailBase(BaseModel):
    """Base schema for event record detail."""

    heart_rate_min: Decimal | int | None = None
    heart_rate_max: Decimal | int | None = None
    heart_rate_avg: Decimal | None = None

    steps_count: int | None = None
    energy_burned: Decimal | None = None
    distance: Decimal | None = None

    max_speed: Decimal | None = None
    max_watts: Decimal | None = None

    average_speed: Decimal | None = None
    average_cadence: Decimal | None = None
    average_watts: Decimal | None = None

    moving_time_seconds: int | None = None
    total_elevation_gain: Decimal | None = None

    elev_high: Decimal | None = None
    elev_low: Decimal | None = None

    # Sleep-specific fields
    sleep_total_duration_minutes: int | None = None
    sleep_time_in_bed_minutes: int | None = None
    sleep_efficiency_score: Decimal | None = None
    sleep_deep_minutes: int | None = None
    sleep_rem_minutes: int | None = None
    sleep_light_minutes: int | None = None
    sleep_awake_minutes: int | None = None
    is_nap: bool | None = None

    sleep_stages: list[SleepStage] | None = None

    segments: list[dict] | None = None
    hr_zones: HRZones | None = None
    power_zones: PowerZones | None = None

    entry_source: EntrySource | None = None
    intensity: WorkoutIntensity | None = None
    label: str | None = Field(default=None, max_length=LABEL_MAX_LENGTH)

    @field_validator("label", mode="before")
    @classmethod
    def _truncate_label(cls, value: str | None) -> str | None:
        """Labels are provider free text, so truncate rather than fail the whole batch."""
        if isinstance(value, str) and len(value) > LABEL_MAX_LENGTH:
            return value[:LABEL_MAX_LENGTH]
        return value


class EventRecordDetailCreate(EventRecordDetailBase):
    """Schema for creating an event record detail entry."""

    record_id: UUID


class EventRecordDetailUpdate(EventRecordDetailBase):
    """Schema for updating an event record detail entry."""


class EventRecordDetailResponse(EventRecordDetailBase):
    """Schema returned to API consumers."""

    record_id: UUID
