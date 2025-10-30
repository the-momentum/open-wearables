from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class WorkoutCreate(BaseModel):
    """Schema for creating a workout."""

    id: UUID
    user_id: UUID
    name: str | None = None
    location: str | None = None
    start: datetime
    end: datetime
    duration: Decimal | None = None
    active_energy_burned_qty: Decimal | None = None
    active_energy_burned_units: str | None = None
    distance_qty: Decimal | None = None
    distance_units: str | None = None
    intensity_qty: Decimal | None = None
    intensity_units: str | None = None
    humidity_qty: Decimal | None = None
    humidity_units: str | None = None
    temperature_qty: Decimal | None = None
    temperature_units: str | None = None


class WorkoutUpdate(BaseModel):
    """Schema for updating a workout."""

    name: str | None = None
    location: str | None = None
    start: datetime | None = None
    end: datetime | None = None
    duration: Decimal | None = None
    active_energy_burned_qty: Decimal | None = None
    active_energy_burned_units: str | None = None
    distance_qty: Decimal | None = None
    distance_units: str | None = None
    intensity_qty: Decimal | None = None
    intensity_units: str | None = None
    humidity_qty: Decimal | None = None
    humidity_units: str | None = None
    temperature_qty: Decimal | None = None
    temperature_units: str | None = None
