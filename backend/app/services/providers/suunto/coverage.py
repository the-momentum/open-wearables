from app.schemas.enums import SeriesType
from app.schemas.enums.health_score_category import HealthScoreCategory

TIMESERIES: frozenset[SeriesType] = frozenset([
    SeriesType.energy,
    SeriesType.heart_rate,
    SeriesType.heart_rate_variability_rmssd,
    SeriesType.oxygen_saturation,
    SeriesType.resting_heart_rate,
    SeriesType.steps,
])

WORKOUT_FIELDS: frozenset[str] = frozenset([
    "heart_rate_min",
    "heart_rate_max",
    "heart_rate_avg",
    "steps_count",
    "energy_burned",
    "distance",
    "max_speed",
    "max_watts",
    "average_speed",
    "average_watts",
    "moving_time_seconds",
    "total_elevation_gain",
    "elev_high",
    "elev_low",
])

SLEEP_FIELDS: frozenset[str] = frozenset([
    "sleep_total_duration_minutes",
    "sleep_time_in_bed_minutes",
    "sleep_efficiency_score",
    "sleep_deep_minutes",
    "sleep_rem_minutes",
    "sleep_light_minutes",
    "sleep_awake_minutes",
    "is_nap",
])

HEALTH_SCORES: frozenset[HealthScoreCategory] = frozenset([
    HealthScoreCategory.RECOVERY,
])
