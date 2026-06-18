from app.schemas.enums import SeriesType
from app.schemas.enums.health_score_category import HealthScoreCategory

TIMESERIES: frozenset[SeriesType] = frozenset([
    SeriesType.distance_walking_running,
    SeriesType.energy,
    SeriesType.heart_rate,
    SeriesType.heart_rate_variability_rmssd,
    SeriesType.oxygen_saturation,
    SeriesType.skin_temperature,
    SeriesType.skin_temperature_deviation,
    SeriesType.steps,
])

WORKOUT_FIELDS: frozenset[str] = frozenset([
    "heart_rate_max",
    "heart_rate_avg",
    "energy_burned",
    "distance",
])

SLEEP_FIELDS: frozenset[str] = frozenset([
    "sleep_total_duration_minutes",
    "sleep_time_in_bed_minutes",
    "sleep_deep_minutes",
    "sleep_rem_minutes",
    "sleep_light_minutes",
    "sleep_awake_minutes",
    "sleep_stages",
])

HEALTH_SCORES: frozenset[HealthScoreCategory] = frozenset([
    HealthScoreCategory.SLEEP,
    HealthScoreCategory.STRAIN,
    HealthScoreCategory.RECOVERY,
    HealthScoreCategory.READINESS,
])
