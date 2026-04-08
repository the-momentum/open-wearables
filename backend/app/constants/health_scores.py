from typing import NamedTuple

from app.schemas.enums import HealthScoreCategory, ProviderName


class ScoreRange(NamedTuple):
    min: int
    max: int


HEALTH_SCORE_RANGES: dict[HealthScoreCategory, dict[ProviderName, ScoreRange]] = {
    HealthScoreCategory.SLEEP: {
        ProviderName.INTERNAL: ScoreRange(0, 100),
        ProviderName.OURA: ScoreRange(1, 100),
    },
    HealthScoreCategory.READINESS: {
        ProviderName.OURA: ScoreRange(1, 100),
    },
    HealthScoreCategory.ACTIVITY: {
        ProviderName.OURA: ScoreRange(1, 100),
    },
}
