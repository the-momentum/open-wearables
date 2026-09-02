from app.schemas.enums import SeriesType
from app.schemas.enums.health_score_category import HealthScoreCategory

# Timeseries mappings (handler key → SeriesType) consumed directly by data_247.py.
ACTIVITY_SERIES: dict[str, SeriesType] = {
    "heart_rate": SeriesType.heart_rate,
    "steps": SeriesType.steps,
    "spo2": SeriesType.oxygen_saturation,
    "energy": SeriesType.energy,
    # Suunto provides RMSSD-based HRV, map to the correct series type
    "hrv": SeriesType.heart_rate_variability_rmssd,
}
DAILY_STAT_SERIES: dict[str, SeriesType] = {
    "stepcount": SeriesType.steps,
    "energyconsumption": SeriesType.energy,
}
# Per-night scalars carried inside a sleep entry (normalized key → SeriesType).
SLEEP_SERIES: dict[str, SeriesType] = {
    "min_heart_rate_bpm": SeriesType.resting_heart_rate,
    "avg_hrv_ms": SeriesType.heart_rate_variability_rmssd,
    "max_spo2_percent": SeriesType.oxygen_saturation,
}

TIMESERIES: frozenset[SeriesType] = frozenset(
    {
        *ACTIVITY_SERIES.values(),  # /247samples/activity
        *DAILY_STAT_SERIES.values(),  # /247/daily-activity-statistics
        *SLEEP_SERIES.values(),  # /247samples/sleep
    }
)

WORKOUT_FIELDS: frozenset[str] = frozenset(
    {
        "heart_rate_min",
        "heart_rate_max",
        "heart_rate_avg",
        "steps_count",
        "energy_burned",
        "distance",
        "max_speed",
        "max_watts",
        "average_speed",
        "average_watts",
        "moving_time_seconds",
        "total_elevation_gain",
        "elev_high",
        "elev_low",
    }
)

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
    }
)
