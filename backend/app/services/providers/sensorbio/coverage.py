"""Sensor Bio coverage declaration — single source of truth for emitted data.

Powers GET /api/v1/meta/coverage and the Data Coverage matrix. Mapping tables
here are imported by data_247.py so TIMESERIES cannot drift from the
implementation.
"""

from app.schemas.enums import SeriesType
from app.schemas.enums.health_score_category import HealthScoreCategory

# Continuous /v1/biometrics samples (handler key → SeriesType).
ACTIVITY_SAMPLE_SERIES: dict[str, SeriesType] = {
    "heart_rate": SeriesType.heart_rate,
    "heart_rate_variability": SeriesType.heart_rate_variability_rmssd,
    "spo2": SeriesType.oxygen_saturation,
    "respiratory_rate": SeriesType.respiratory_rate,
}

# Daily recovery biometric snapshots from /v1/scores (handler key → SeriesType).
RECOVERY_SERIES: dict[str, SeriesType] = {
    "resting_heart_rate": SeriesType.resting_heart_rate,
    "hrv_rmssd_milli": SeriesType.heart_rate_variability_rmssd,
    "spo2_percentage": SeriesType.oxygen_saturation,
}

# Daily totals from /v1/step/details (handler key → SeriesType).
DAILY_ACTIVITY_SERIES: dict[str, SeriesType] = {
    "steps": SeriesType.steps,
    "energy": SeriesType.energy,
    "distance": SeriesType.distance_walking_running,
}

TIMESERIES: frozenset[SeriesType] = frozenset(
    {
        *ACTIVITY_SAMPLE_SERIES.values(),  # /v1/biometrics
        *RECOVERY_SERIES.values(),  # /v1/scores biometric averages
        *DAILY_ACTIVITY_SERIES.values(),  # /v1/step/details
    }
)

# EventRecordDetail fields populated by workouts.py
WORKOUT_FIELDS: frozenset[str] = frozenset(
    {
        "heart_rate_avg",
        "heart_rate_max",
        "heart_rate_min",
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
    }
)

HEALTH_SCORES: frozenset[HealthScoreCategory] = frozenset(
    {
        HealthScoreCategory.RECOVERY,
        HealthScoreCategory.ACTIVITY,
        HealthScoreCategory.SLEEP,
    }
)
