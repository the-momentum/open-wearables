from app.schemas.enums import SeriesType
from app.schemas.enums.health_score_category import HealthScoreCategory

TIMESERIES: frozenset[SeriesType] = frozenset([
    SeriesType.breathing_disturbance_index,
    SeriesType.cardiovascular_age,
    SeriesType.distance_walking_running,
    SeriesType.energy,
    SeriesType.heart_rate,
    SeriesType.heart_rate_variability_rmssd,
    SeriesType.height,
    SeriesType.oxygen_saturation,
    SeriesType.respiratory_rate,
    SeriesType.skin_temperature_deviation,
    SeriesType.skin_temperature_trend_deviation,
    SeriesType.steps,
    SeriesType.vo2_max,
    SeriesType.weight,
])

WORKOUT_FIELDS: frozenset[str] = frozenset([
    "energy_burned",
    "distance",
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
    "sleep_stages",
])

HEALTH_SCORES: frozenset[HealthScoreCategory] = frozenset([
    HealthScoreCategory.ACTIVITY,
    HealthScoreCategory.READINESS,
    HealthScoreCategory.SLEEP,
])
