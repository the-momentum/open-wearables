from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.apple.workout_statistics import WorkoutStatisticIn
from app.schemas.apple.healthkit.workout_import import WorkoutIn as HKWorkoutIn


class WorkoutIn(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
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


class HeartRateDataIn(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    workout_id: UUID
    date: datetime
    source: str | None = None
    units: str | None = None
    avg: Decimal | None = None
    min: Decimal | None = None
    max: Decimal | None = None


class HeartRateRecoveryIn(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    workout_id: UUID
    date: datetime
    source: str | None = None
    units: str | None = None
    avg: Decimal | None = None
    min: Decimal | None = None
    max: Decimal | None = None


class ActiveEnergyIn(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    workout_id: UUID
    date: datetime
    source: str | None = None
    units: str | None = None
    qty: Decimal | None = None


class ImportBundle(BaseModel):
    """
    Container returned by the factory:
    - workout: WorkoutIn
    - workout_statistics: list[WorkoutStatisticIn]
    - heart_rate_data: list[HeartRateDataIn]
    - heart_rate_recovery: list[HeartRateRecoveryIn]
    - active_energy: list[ActiveEnergyIn]
    """

    model_config = ConfigDict(from_attributes=True)

    workout: HKWorkoutIn
    workout_statistics: list[WorkoutStatisticIn] = []
    heart_rate_data: list[HeartRateDataIn] = []
    heart_rate_recovery: list[HeartRateRecoveryIn] = []
    active_energy: list[ActiveEnergyIn] = []
