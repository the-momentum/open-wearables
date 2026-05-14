from enum import StrEnum

from pydantic import BaseModel


class TemperatureMeasurementType(StrEnum):
    UNKNOWN = "TM_UNKNOWN"
    SKIN_TEMPERATURE = "TM_SKIN_TEMPERATURE"
    CORE_TEMPERATURE = "TM_CORE_TEMPERATURE"


class TemperatureSensorLocation(StrEnum):
    UNKNOWN = "SL_UNKNOWN"
    DISTAL = "SL_DISTAL"
    PROXIMAL = "SL_PROXIMAL"


class BodyTemperatureSampleJSON(BaseModel):
    temperature_celsius: float | None = None
    recording_time_delta_milliseconds: int | None = None


class BodyTemperaturePeriodJSON(BaseModel):
    source_device_id: str | None = None
    measurement_type: TemperatureMeasurementType | None = None
    sensor_location: TemperatureSensorLocation | None = None
    start_time: str | None = None
    end_time: str | None = None
    modified_time: str | None = None
    samples: list[BodyTemperatureSampleJSON] | None = None
