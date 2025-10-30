from __future__ import annotations

from pydantic import BaseModel


class DistanceValue(BaseModel):
    """Distance value with unit."""

    value: float
    unit: str = "km"


class ActiveEnergyValue(BaseModel):
    """Active energy value with unit."""

    value: float
    unit: str = "kJ"


class IntensityValue(BaseModel):
    """Intensity value with unit."""

    value: float
    unit: str = "kcal/hr·kg"


class TemperatureValue(BaseModel):
    """Temperature value with unit."""

    value: float
    unit: str = "degC"


class HumidityValue(BaseModel):
    """Humidity value with unit."""

    value: float
    unit: str = "%"
