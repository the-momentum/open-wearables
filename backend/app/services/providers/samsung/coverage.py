from app.constants.series_types.sdk.metric_types import SAMSUNG_METRIC_TYPE_TO_SERIES_TYPE
from app.constants.series_types.sdk.workout_statistics import SAMSUNG_WORKOUT_STATISTIC_TYPE_TO_SERIES_TYPE
from app.schemas.enums import HealthScoreCategory, SeriesType
from app.services.providers.apple.coverage import MEAL_FIELDS, SLEEP_FIELDS

# Samsung Health Data SDK exposes a narrower set than Health Connect, so Samsung
# declares exactly what SamsungHealthManager emits instead of reusing Android/Apple.
# Dietary types the SDK never sends (caffeine, chloride, extended vitamins/minerals) are excluded.
TIMESERIES: frozenset[SeriesType] = frozenset(
    {
        *SAMSUNG_METRIC_TYPE_TO_SERIES_TYPE.values(),
        *SAMSUNG_WORKOUT_STATISTIC_TYPE_TO_SERIES_TYPE.values(),
    }
)

# EventRecordDetail fields filled from Samsung ExerciseSession values by the shared SDK import service
WORKOUT_FIELDS: frozenset[str] = frozenset(
    {
        "heart_rate_min",
        "heart_rate_max",
        "heart_rate_avg",
        "energy_burned",
        "distance",
        "max_speed",
        "average_speed",
        "total_elevation_gain",
        "elev_high",
        "elev_low",
    }
)

# SamsungHealthManager forwards SleepType.SLEEP_SCORE as a `sleepScore` value on each sleep entry
HEALTH_SCORES: frozenset[HealthScoreCategory] = frozenset({HealthScoreCategory.SLEEP})

__all__ = ["HEALTH_SCORES", "MEAL_FIELDS", "SLEEP_FIELDS", "TIMESERIES", "WORKOUT_FIELDS"]
