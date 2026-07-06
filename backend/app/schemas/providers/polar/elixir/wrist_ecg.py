from enum import StrEnum

from pydantic import BaseModel


class EcgHrvLevel(StrEnum):
    NO_BASELINE = "ECG_HRV_LEVEL_NO_BASELINE"
    BELOW_USUAL = "ECG_HRV_LEVEL_BELOW_USUAL"
    USUAL = "ECG_HRV_LEVEL_USUAL"
    ABOVE_USUAL = "ECG_HRV_LEVEL_ABOVE_USUAL"


class EcgQualityLevel(StrEnum):
    UNKNOWN = "ECG_QUALITY_UNKNOWN"
    NO_CONTACT = "ECG_QUALITY_NO_CONTACT"
    LOW = "ECG_QUALITY_LOW"
    HIGH = "ECG_QUALITY_HIGH"


class EcgSampleJSON(BaseModel):
    recording_time_delta_ms: int | None = None
    amplitude_mv: float | None = None


class EcgQualityMeasurementJSON(BaseModel):
    recording_time_delta_ms: int | None = None
    quality_level: EcgQualityLevel | None = None


class EcgTestResultJSON(BaseModel):
    source_device_id: str | None = None
    test_time: int | None = None
    time_zone_offset: int | None = None
    average_heart_rate_bpm: int | None = None
    heart_rate_variability_ms: float | None = None
    heart_rate_variability_level: EcgHrvLevel | None = None
    rri_ms: float | None = None
    pulse_transit_time_systolic_ms: float | None = None
    pulse_transit_time_diastolic_ms: float | None = None
    pulse_transit_time_quality_index: float | None = None
    samples: list[EcgSampleJSON] | None = None
    quality_measurements: list[EcgQualityMeasurementJSON] | None = None
