from app.schemas.enums import SeriesType
from app.schemas.enums.health_score_category import HealthScoreCategory

# Daily-activity mapping (DailyActivityJSON attribute → SeriesType) consumed
# directly by data_247.normalize_daily_activity via /v3/users/activities.
ACTIVITY_SERIES: dict[str, SeriesType] = {
    "steps": SeriesType.steps,
    "active_calories": SeriesType.energy,
    "distance_from_steps": SeriesType.distance_walking_running,
    "active_time_minutes": SeriesType.active_time,
}

TIMESERIES: frozenset[SeriesType] = frozenset(
    {
        *ACTIVITY_SERIES.values(),  # /v3/users/activities
        SeriesType.heart_rate,  # /v3/users/sleep + /v3/users/continuous-heart-rate + /v3/users/wrist-ecg
        SeriesType.heart_rate_variability_rmssd,  # /v3/users/spo2 + /v3/users/wrist-ecg
        SeriesType.oxygen_saturation,  # /v3/users/spo2
        SeriesType.skin_temperature,  # /v3/users/sleep-skin-temperature + /v3/users/body-temperature (SKIN)
        SeriesType.skin_temperature_deviation,  # /v3/users/sleep-skin-temperature (deviation_from_baseline)
        SeriesType.body_temperature,  # /v3/users/body-temperature (CORE)
    }
)

# EventRecordDetail fields populated by workouts.py (workout records)
WORKOUT_FIELDS: frozenset[str] = frozenset(
    {
        "heart_rate_max",
        "heart_rate_avg",
        "energy_burned",
        "distance",
    }
)

# EventRecordDetail fields populated by data_247.py (sleep records)
SLEEP_FIELDS: frozenset[str] = frozenset(
    {
        "sleep_total_duration_minutes",
        "sleep_time_in_bed_minutes",
        "sleep_deep_minutes",
        "sleep_rem_minutes",
        "sleep_light_minutes",
        "sleep_awake_minutes",
        "sleep_stages",
    }
)

HEALTH_SCORES: frozenset[HealthScoreCategory] = frozenset(
    {
        HealthScoreCategory.SLEEP,
        HealthScoreCategory.STRAIN,
        HealthScoreCategory.RECOVERY,
        HealthScoreCategory.READINESS,
    }
)
