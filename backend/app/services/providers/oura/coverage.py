from app.schemas.enums import SeriesType
from app.schemas.enums.health_score_category import HealthScoreCategory

# Timeseries mappings (handler key → SeriesType) consumed directly by data_247.py.
ACTIVITY_SERIES: dict[str, SeriesType] = {
    "steps": SeriesType.steps,
    "energy": SeriesType.energy,
    "distance": SeriesType.distance_walking_running,
    "active_time": SeriesType.active_time,
}
READINESS_SERIES: dict[str, SeriesType] = {
    "temperature_deviation": SeriesType.skin_temperature_deviation,
    "temperature_trend_deviation": SeriesType.skin_temperature_trend_deviation,
}
SLEEP_INTERVAL_SERIES: dict[str, SeriesType] = {
    "heart_rate": SeriesType.heart_rate,
    "hrv": SeriesType.heart_rate_variability_rmssd,
}
SLEEP_SCALAR_SERIES: dict[str, SeriesType] = {
    "average_breath": SeriesType.respiratory_rate,
    "lowest_heart_rate": SeriesType.resting_heart_rate,
}
PERSONAL_INFO_SERIES: dict[str, SeriesType] = {
    "weight": SeriesType.weight,
    "height": SeriesType.height,
}

TIMESERIES: frozenset[SeriesType] = frozenset(
    {
        *ACTIVITY_SERIES.values(),  # /v2/usercollection/daily_activity
        *READINESS_SERIES.values(),  # /v2/usercollection/daily_readiness
        *SLEEP_INTERVAL_SERIES.values(),  # /v2/usercollection/sleep (intervals)
        *SLEEP_SCALAR_SERIES.values(),  # /v2/usercollection/sleep (per-night scalars)
        *PERSONAL_INFO_SERIES.values(),  # /v2/usercollection/personal_info
        SeriesType.oxygen_saturation,  # /v2/usercollection/daily_spo2
        SeriesType.breathing_disturbance_index,  # /v2/usercollection/daily_spo2
        SeriesType.vo2_max,  # /v2/usercollection/vO2_max
        SeriesType.cardiovascular_age,  # /v2/usercollection/daily_cardiovascular_age
    }
)

# EventRecordDetail fields populated by workouts.py (workout records)
WORKOUT_FIELDS: frozenset[str] = frozenset(
    {
        "energy_burned",
        "distance",
        "moving_time_seconds",
    }
)

# EventRecordDetail fields populated by data_247.py (sleep records)
SLEEP_FIELDS: frozenset[str] = frozenset(
    {
        "sleep_total_duration_minutes",
        "sleep_time_in_bed_minutes",
        "sleep_efficiency_score",
        "sleep_deep_minutes",
        "sleep_rem_minutes",
        "sleep_light_minutes",
        "sleep_awake_minutes",
        "is_nap",
        "sleep_stages",
    }
)

HEALTH_SCORES: frozenset[HealthScoreCategory] = frozenset(
    {
        HealthScoreCategory.ACTIVITY,
        HealthScoreCategory.READINESS,
        HealthScoreCategory.SLEEP,
    }
)
