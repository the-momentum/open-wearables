# ruff: noqa: N815

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class QuantityJSON(BaseModel):
    qty: float | int | None = None
    units: str | None = None


class HeartRateEntryJSON(BaseModel):
    avg: float | None = Field(default=None, alias="Avg")
    min: float | None = Field(default=None, alias="Min")
    max: float | None = Field(default=None, alias="Max")
    units: str | None = None
    date: str
    source: str | None = None

    @field_validator("date")
    @classmethod
    def parse_date(cls, v: str) -> str:
        return v


class ActiveEnergyEntryJSON(BaseModel):
    qty: float | int | None = None
    units: str | None = None
    date: str
    source: str | None = None


class WorkoutJSON(BaseModel):
    id: str | None = None
    name: str | None = None
    location: str | None = None
    start: str
    end: str
    duration: float | None = None

    activeEnergyBurned: QuantityJSON | None = None
    distance: QuantityJSON | None = None
    intensity: QuantityJSON | None = None
    humidity: QuantityJSON | None = None
    temperature: QuantityJSON | None = None

    heartRateData: list[HeartRateEntryJSON] | None = None
    heartRateRecovery: list[HeartRateEntryJSON] | None = None
    activeEnergy: list[ActiveEnergyEntryJSON] | None = None

    metadata: dict[str, Any] = Field(default_factory=dict)
