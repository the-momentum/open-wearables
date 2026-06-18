from app.schemas.enums import SeriesType
from app.schemas.enums.health_score_category import HealthScoreCategory

TIMESERIES: frozenset[SeriesType] = frozenset([
    SeriesType.heart_rate_variability_rmssd,
    SeriesType.height,
    SeriesType.oxygen_saturation,
    SeriesType.resting_heart_rate,
    SeriesType.skin_temperature,
    SeriesType.weight,
])

WORKOUT_FIELDS: frozenset[str] = frozenset([
    "heart_rate_avg",
    "heart_rate_max",
    "energy_burned",
    "distance",
    "total_elevation_gain",
    "moving_time_seconds",
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
    HealthScoreCategory.SLEEP,
    HealthScoreCategory.RECOVERY,
    HealthScoreCategory.STRAIN,
])
