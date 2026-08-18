from app.schemas.enums import SeriesType
from app.schemas.enums.health_score_category import HealthScoreCategory

# Timeseries mappings (handler key → SeriesType) consumed directly by data_247.py.
RECOVERY_SERIES: dict[str, SeriesType] = {
    "resting_heart_rate": SeriesType.resting_heart_rate,
    "hrv_rmssd_milli": SeriesType.heart_rate_variability_rmssd,
    "spo2_percentage": SeriesType.oxygen_saturation,
    "skin_temp_celsius": SeriesType.skin_temperature,
}

TIMESERIES: frozenset[SeriesType] = frozenset(
    {
        *RECOVERY_SERIES.values(),  # /v2/recovery
        SeriesType.height,  # /v2/user/measurement/body
        SeriesType.weight,  # /v2/user/measurement/body
    }
)

# EventRecordDetail fields populated by workouts.py (workout records)
WORKOUT_FIELDS: frozenset[str] = frozenset(
    {
        "heart_rate_avg",
        "heart_rate_max",
        "energy_burned",
        "distance",
        "total_elevation_gain",
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
    }
)

HEALTH_SCORES: frozenset[HealthScoreCategory] = frozenset(
    {
        HealthScoreCategory.SLEEP,
        HealthScoreCategory.RECOVERY,
        HealthScoreCategory.STRAIN,
    }
)
