from app.schemas.enums import SeriesType
from app.schemas.enums.health_score_category import HealthScoreCategory

# Fitbit currently has no timeseries (247) or sleep processing — workouts only.
TIMESERIES: frozenset[SeriesType] = frozenset()

# EventRecordDetail fields populated by workouts.py (_build_metrics)
WORKOUT_FIELDS: frozenset[str] = frozenset(
    {
        "heart_rate_min",
        "heart_rate_max",
        "heart_rate_avg",
        "steps_count",
        "energy_burned",
        "distance",
    }
)

SLEEP_FIELDS: frozenset[str] = frozenset()
HEALTH_SCORES: frozenset[HealthScoreCategory] = frozenset()
