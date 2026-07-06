from enum import StrEnum

from pydantic import BaseModel

from .alertness import AlertnessValidity


class CircadianBedtimeQuality(StrEnum):
    UNKNOWN = "CIRCADIAN_BEDTIME_QUALITY_UNKNOWN"
    WEAK = "CIRCADIAN_BEDTIME_QUALITY_WEAK"
    COMPROMISED = "CIRCADIAN_BEDTIME_QUALITY_COMPROMISED"
    CLEARLY_RECOGNIZABLE = "CIRCADIAN_BEDTIME_QUALITY_CLEARLY_RECOGNIZABLE"


class CircadianBedtimeResultType(StrEnum):
    UNKNOWN = "CIRCADIAN_BEDTIME_TYPE_UNKNOWN"
    PREDICTION = "CIRCADIAN_BEDTIME_TYPE_PREDICTION"
    HISTORY = "CIRCADIAN_BEDTIME_TYPE_HISTORY"


class CircadianBedtimeJSON(BaseModel):
    validity: AlertnessValidity | None = None
    quality: CircadianBedtimeQuality | None = None
    result_type: CircadianBedtimeResultType | None = None
    period_start_time: str | None = None
    period_end_time: str | None = None
    preferred_sleep_period_start_time: str | None = None
    preferred_sleep_period_end_time: str | None = None
    sleep_gate_start_time: str | None = None
    sleep_gate_end_time: str | None = None
    sleep_timezone_offset_minutes: int | None = None
