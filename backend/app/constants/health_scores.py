from typing import NamedTuple

from app.schemas.enums import HealthScoreCategory, ProviderName


class ScoreRange(NamedTuple):
    min: int
    max: int


HEALTH_SCORE_RANGES: dict[HealthScoreCategory, dict[ProviderName, ScoreRange]] = {
    HealthScoreCategory.SLEEP: {
        ProviderName.INTERNAL: ScoreRange(0, 100),
        ProviderName.OURA: ScoreRange(1, 100),
        ProviderName.GARMIN: ScoreRange(1, 100),
        ProviderName.WHOOP: ScoreRange(0, 100),
    },
    HealthScoreCategory.READINESS: {
        ProviderName.OURA: ScoreRange(1, 100),
    },
    HealthScoreCategory.ACTIVITY: {
        ProviderName.OURA: ScoreRange(1, 100),
    },
    HealthScoreCategory.STRESS: {
        ProviderName.GARMIN: ScoreRange(0, 100),
    },
    HealthScoreCategory.BODY_BATTERY: {
        ProviderName.GARMIN: ScoreRange(0, 100),
    },
    HealthScoreCategory.RECOVERY: {
        ProviderName.WHOOP: ScoreRange(0, 100),
        ProviderName.SUUNTO: ScoreRange(0, 100),
    },
    HealthScoreCategory.STRAIN: {
        ProviderName.WHOOP: ScoreRange(0, 21),
    },
}
