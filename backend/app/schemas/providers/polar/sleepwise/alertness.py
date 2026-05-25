from enum import StrEnum

from pydantic import BaseModel


class GradeType(StrEnum):
    UNKNOWN = "GRADE_TYPE_UNKNOWN"
    PRIMARY = "GRADE_TYPE_PRIMARY"
    ADDITIONAL = "GRADE_TYPE_ADDITIONAL"


class GradeClassification(StrEnum):
    UNKNOWN = "GRADE_CLASSIFICATION_UNKNOWN"
    WEAK = "GRADE_CLASSIFICATION_WEAK"
    FAIR = "GRADE_CLASSIFICATION_FAIR"
    STRONG = "GRADE_CLASSIFICATION_STRONG"
    EXCELLENT = "GRADE_CLASSIFICATION_EXCELLENT"


class AlertnessValidity(StrEnum):
    UNKNOWN = "VALIDITY_UNKNOWN"
    RESET = "VALIDITY_RESET"
    NOT_VALID = "VALIDITY_NOT_VALID"
    ESTIMATE = "VALIDITY_ESTIMATE"
    VALID = "VALIDITY_VALID"


class SleepInertia(StrEnum):
    UNKNOWN = "SLEEP_INERTIA_UNKNOWN"
    NO_INERTIA = "SLEEP_INERTIA_NO_INERTIA"
    MILD = "SLEEP_INERTIA_MILD"
    MODERATE = "SLEEP_INERTIA_MODERATE"
    HEAVY = "SLEEP_INERTIA_HEAVY"


class SleepType(StrEnum):
    UNKNOWN = "SLEEP_TYPE_UNKNOWN"
    PRIMARY = "SLEEP_TYPE_PRIMARY"
    SECONDARY = "SLEEP_TYPE_SECONDARY"
    ARTIFICIAL = "SLEEP_TYPE_ARTIFICIAL"


class AlertnessResultType(StrEnum):
    UNKNOWN = "ALERTNESS_TYPE_UNKNOWN"
    PREDICTION = "ALERTNESS_TYPE_PREDICTION"
    HISTORY = "ALERTNESS_TYPE_HISTORY"


class AlertnessLevel(StrEnum):
    UNKNOWN = "ALERTNESS_LEVEL_UNKNOWN"
    MINIMAL = "ALERTNESS_LEVEL_MINIMAL"
    VERY_LOW = "ALERTNESS_LEVEL_VERY_LOW"
    LOW = "ALERTNESS_LEVEL_LOW"
    HIGH = "ALERTNESS_LEVEL_HIGH"
    VERY_HIGH = "ALERTNESS_LEVEL_VERY_HIGH"


class AlertnessHourlyDataJSON(BaseModel):
    validity: AlertnessValidity | None = None
    alertness_level: AlertnessLevel | None = None
    start_time: str | None = None
    end_time: str | None = None


class AlertnessJSON(BaseModel):
    grade: float | None = None
    grade_validity_seconds: int | None = None
    grade_type: GradeType | None = None
    grade_classification: GradeClassification | None = None
    validity: AlertnessValidity | None = None
    sleep_inertia: SleepInertia | None = None
    sleep_type: SleepType | None = None
    result_type: AlertnessResultType | None = None
    period_start_time: str | None = None
    period_end_time: str | None = None
    sleep_period_start_time: str | None = None
    sleep_period_end_time: str | None = None
    sleep_timezone_offset_minutes: int | None = None
    hourly_data: list[AlertnessHourlyDataJSON] | None = None
