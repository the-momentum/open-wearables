from app.schemas.enums import SeriesType

TIMESERIES: frozenset[SeriesType] = frozenset([
    SeriesType.body_temperature,
    SeriesType.heart_rate,
    SeriesType.heart_rate_variability_sdnn,
    SeriesType.steps,
    SeriesType.vo2_max,
])

SLEEP_FIELDS: frozenset[str] = frozenset([
    "sleep_total_duration_minutes",
    "sleep_time_in_bed_minutes",
    "sleep_efficiency_score",
    "sleep_deep_minutes",
    "sleep_rem_minutes",
    "sleep_light_minutes",
    "sleep_awake_minutes",
    "is_nap",
])
