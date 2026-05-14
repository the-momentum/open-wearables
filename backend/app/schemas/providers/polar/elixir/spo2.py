from enum import StrEnum

from pydantic import BaseModel


class Spo2TestStatus(StrEnum):
    PASSED = "SPO2_TEST_PASSED"
    INCONCLUSIVE_TOO_LOW_QUALITY_IN_SAMPLES = "SPO2_TEST_INCONCLUSIVE_TOO_LOW_QUALITY_IN_SAMPLES"
    INCONCLUSIVE_TOO_LOW_OVERALL_QUALITY = "SPO2_TEST_INCONCLUSIVE_TOO_LOW_OVERALL_QUALITY"
    INCONCLUSIVE_TOO_MANY_MISSING_SAMPLES = "SPO2_TEST_INCONCLUSIVE_TOO_MANY_MISSING_SAMPLES"


class Spo2Class(StrEnum):
    UNKNOWN = "SPO2_CLASS_UNKNOWN"
    VERY_LOW = "SPO2_CLASS_VERY_LOW"
    LOW = "SPO2_CLASS_LOW"
    NORMAL = "SPO2_CLASS_NORMAL"


class DeviationFromBaseline(StrEnum):
    NO_BASELINE = "DEVIATION_NO_BASELINE"
    BELOW_USUAL = "DEVIATION_BELOW_USUAL"
    USUAL = "DEVIATION_USUAL"
    ABOVE_USUAL = "DEVIATION_ABOVE_USUAL"


class Spo2TestResultJSON(BaseModel):
    source_device_id: str | None = None
    test_time: int | None = None
    time_zone_offset: int | None = None
    test_status: Spo2TestStatus | None = None
    blood_oxygen_percent: int | None = None
    spo2_class: Spo2Class | None = None
    spo2_value_deviation_from_baseline: DeviationFromBaseline | None = None
    spo2_quality_average_percent: float | None = None
    average_heart_rate_bpm: int | None = None
    heart_rate_variability_ms: float | None = None
    spo2_hrv_deviation_from_baseline: DeviationFromBaseline | None = None
    altitude_meters: float | None = None
