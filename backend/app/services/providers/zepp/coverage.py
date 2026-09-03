from app.schemas.enums import SeriesType
from app.schemas.enums.health_score_category import HealthScoreCategory

TIMESERIES: frozenset[SeriesType] = frozenset(
    {
        SeriesType.heart_rate,
        SeriesType.resting_heart_rate,
        SeriesType.heart_rate_variability_rmssd,
        SeriesType.steps,
        SeriesType.energy,
        SeriesType.distance_walking_running,
        SeriesType.vo2_max,
        SeriesType.weight,
        SeriesType.body_mass_index,
        SeriesType.oxygen_saturation,
    }
)

WORKOUT_FIELDS: frozenset[str] = frozenset(
    {
        "heart_rate_max",
        "heart_rate_avg",
        "steps_count",
        "energy_burned",
        "distance",
        "moving_time_seconds",
    }
)

SLEEP_FIELDS: frozenset[str] = frozenset(
    {
        "sleep_total_duration_minutes",
        "sleep_time_in_bed_minutes",
        "sleep_deep_minutes",
        "sleep_light_minutes",
        "sleep_rem_minutes",
        "sleep_awake_minutes",
    }
)

HEALTH_SCORES: frozenset[HealthScoreCategory] = frozenset(
    {
        HealthScoreCategory.READINESS,
        HealthScoreCategory.STRESS,
        HealthScoreCategory.BODY_BATTERY,
    }
)
