from typing import NamedTuple

from app.schemas.enums import SeriesType
from app.schemas.enums.health_score_category import HealthScoreCategory

# Timeseries mappings (handler key → SeriesType) consumed directly by data_247.py.
ACTIVITY_SAMPLE_SERIES: dict[str, SeriesType] = {
    "heart_rate": SeriesType.heart_rate,
    "hrv": SeriesType.heart_rate_variability_rmssd,
    "temperature": SeriesType.skin_temperature,
    "steps": SeriesType.steps,
}


class DailyScalar(NamedTuple):
    """A once-per-day Ultrahuman metric and the object field that holds its number."""

    series_type: SeriesType
    value_field: str


# Earlier entries win when two metrics share a series and day_start_timestamp.
# sleep_rhr is the overnight resting heart rate; night_rhr.avg is the fallback.
DAILY_SCALAR_SERIES: dict[str, DailyScalar] = {
    "vo2_max": DailyScalar(SeriesType.vo2_max, "value"),
    "active_minutes": DailyScalar(SeriesType.active_time, "value"),
    "sleep_rhr": DailyScalar(SeriesType.resting_heart_rate, "value"),
    "night_rhr": DailyScalar(SeriesType.resting_heart_rate, "avg"),
}

TIMESERIES: frozenset[SeriesType] = frozenset(
    {
        *ACTIVITY_SAMPLE_SERIES.values(),  # /user_data/metrics (hr, hrv, temp, steps)
        *(scalar.series_type for scalar in DAILY_SCALAR_SERIES.values()),
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
