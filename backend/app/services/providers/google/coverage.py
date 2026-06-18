from app.constants.series_types.sdk.metric_types import METRIC_TYPE_TO_SERIES_TYPE
from app.schemas.enums import SeriesType

TIMESERIES: frozenset[SeriesType] = frozenset(METRIC_TYPE_TO_SERIES_TYPE.values())

WORKOUT_FIELDS: frozenset[str] = frozenset([
    "heart_rate_min", "heart_rate_max", "heart_rate_avg",
    "steps_count", "energy_burned", "distance",
    "max_speed", "average_speed", "average_cadence",
    "moving_time_seconds", "total_elevation_gain", "elev_high", "elev_low",
])

SLEEP_FIELDS: frozenset[str] = frozenset([
    "sleep_total_duration_minutes", "sleep_time_in_bed_minutes",
    "sleep_efficiency_score", "sleep_deep_minutes", "sleep_rem_minutes",
    "sleep_light_minutes", "sleep_awake_minutes", "is_nap", "sleep_stages",
])
