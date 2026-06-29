from app.schemas.enums import SeriesType
from app.schemas.enums.health_score_category import HealthScoreCategory

# Timeseries mappings (handler key → SeriesType) consumed directly by data_247.py.
ACTIVITY_SAMPLE_SERIES: dict[str, SeriesType] = {
    "heart_rate": SeriesType.heart_rate,
    "hrv": SeriesType.heart_rate_variability_sdnn,
    "temperature": SeriesType.body_temperature,
    "steps": SeriesType.steps,
}

TIMESERIES: frozenset[SeriesType] = frozenset(
    {
        *ACTIVITY_SAMPLE_SERIES.values(),  # /user_data/metrics (hr, hrv, temp, steps)
        SeriesType.vo2_max,  # /user_data/metrics (vo2_max)
        SeriesType.active_time,  # /user_data/metrics (active_minutes)
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
