from app.schemas.enums import SeriesType
from app.schemas.enums.health_score_category import HealthScoreCategory

# Timeseries mappings (handler key → SeriesType) consumed directly by data_247.py.
ACTIVITY_SAMPLE_SERIES: dict[str, SeriesType] = {
    "heart_rate": SeriesType.heart_rate,
    "hrv": SeriesType.heart_rate_variability_rmssd,
    "temperature": SeriesType.skin_temperature,
    "steps": SeriesType.steps,
}

# Single daily values (handler key → SeriesType), each carrying its own day_start_timestamp.
DAILY_SCALAR_SERIES: dict[str, SeriesType] = {
    "vo2_max": SeriesType.vo2_max,
    "active_minutes": SeriesType.active_time,
    "sleep_rhr": SeriesType.resting_heart_rate,
}

TIMESERIES: frozenset[SeriesType] = frozenset(
    {
        *ACTIVITY_SAMPLE_SERIES.values(),  # /user_data/metrics (hr, hrv, temp, steps)
        *DAILY_SCALAR_SERIES.values(),  # /user_data/metrics (vo2_max, active_minutes, sleep_rhr)
    }
)

# Ultrahuman has no workout support.
WORKOUT_FIELDS: frozenset[str] = frozenset()

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

HEALTH_SCORES: frozenset[HealthScoreCategory] = frozenset()
