from app.schemas.enums import SeriesType
from app.schemas.enums.health_score_category import HealthScoreCategory

# Strava is a workouts-only service: no 24/7 timeseries, sleep, or health scores.
TIMESERIES: frozenset[SeriesType] = frozenset()

# EventRecordDetail fields populated by workouts.py (workout records)
WORKOUT_FIELDS: frozenset[str] = frozenset(
    {
        "heart_rate_avg",
        "heart_rate_max",
        "distance",
        "average_speed",
        "max_speed",
        "average_watts",
        "max_watts",
        "total_elevation_gain",
        "elev_high",
        "elev_low",
        "energy_burned",
        "moving_time_seconds",
    }
)

SLEEP_FIELDS: frozenset[str] = frozenset()

HEALTH_SCORES: frozenset[HealthScoreCategory] = frozenset()
