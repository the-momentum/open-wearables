from app.constants.sleep import SleepStageType
from app.schemas.enums import SeriesType
from app.schemas.providers.polar.elixir import TemperatureMeasurementType
from app.schemas.providers.polar.sleepwise import (
    CircadianBedtimeQuality,
    GradeClassification,
    SleepInertia,
)

HYPNOGRAM_STAGE_MAP: dict[int, SleepStageType] = {
    0: SleepStageType.AWAKE,
    1: SleepStageType.REM,
    2: SleepStageType.LIGHT,
    3: SleepStageType.LIGHT,
    4: SleepStageType.DEEP,
    5: SleepStageType.UNKNOWN,
}

BODY_TEMP_SERIES_TYPE: dict[TemperatureMeasurementType, SeriesType] = {
    TemperatureMeasurementType.SKIN_TEMPERATURE: SeriesType.skin_temperature,
    TemperatureMeasurementType.CORE_TEMPERATURE: SeriesType.body_temperature,
}

NIGHTLY_RECHARGE_STATUS_LABELS: dict[int, str] = {
    1: "very poor",
    2: "poor",
    3: "compromised",
    4: "ok",
    5: "good",
    6: "very good",
}

ANS_CHARGE_STATUS_LABELS: dict[int, str] = {
    1: "much below usual",
    2: "below usual",
    3: "usual",
    4: "above usual",
    5: "much above usual",
}

GRADE_CLASSIFICATION_LABELS: dict[GradeClassification, str] = {
    GradeClassification.WEAK: "weak",
    GradeClassification.FAIR: "fair",
    GradeClassification.STRONG: "strong",
    GradeClassification.EXCELLENT: "excellent",
}

SLEEP_INERTIA_LABELS: dict[SleepInertia, str] = {
    SleepInertia.NO_INERTIA: "no inertia",
    SleepInertia.MILD: "mild",
    SleepInertia.MODERATE: "moderate",
    SleepInertia.HEAVY: "heavy",
}

CIRCADIAN_QUALITY_VALUES: dict[CircadianBedtimeQuality, int] = {
    CircadianBedtimeQuality.WEAK: 1,
    CircadianBedtimeQuality.COMPROMISED: 2,
    CircadianBedtimeQuality.CLEARLY_RECOGNIZABLE: 3,
}

CIRCADIAN_QUALITY_LABELS: dict[CircadianBedtimeQuality, str] = {
    CircadianBedtimeQuality.WEAK: "weak",
    CircadianBedtimeQuality.COMPROMISED: "compromised",
    CircadianBedtimeQuality.CLEARLY_RECOGNIZABLE: "clearly recognizable",
}
