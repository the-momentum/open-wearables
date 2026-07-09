from app.schemas.enums import SeriesType
from app.schemas.enums.health_score_category import HealthScoreCategory

# Strava activity stream key (https://developers.strava.com/docs/reference/#api-Streams)
# → SeriesType, consumed by workouts.py. The "time" stream is the per-sample offset
# axis, handled separately and intentionally excluded here.
STREAM_KEY_SERIES_TYPE: dict[str, SeriesType] = {
    "heartrate": SeriesType.heart_rate,
    "velocity_smooth": SeriesType.speed,
    "cadence": SeriesType.cadence,
    "watts": SeriesType.power,
}

# Value for the Strava streams `keys` query param: time axis first, then every metric.
STREAM_KEYS_PARAM: str = ",".join(["time", *STREAM_KEY_SERIES_TYPE])

# Workout-context only, gated by settings.ingest_workout_samples.
TIMESERIES: frozenset[SeriesType] = frozenset(STREAM_KEY_SERIES_TYPE.values())

# EventRecordDetail fields populated by workouts.py (workout records)
WORKOUT_FIELDS: frozenset[str] = frozenset(
    {
        "heart_rate_avg",
        "heart_rate_max",
        "distance",
        "average_speed",
        "max_speed",
        "average_watts",
        "max_watts",
        "total_elevation_gain",
        "elev_high",
        "elev_low",
        "energy_burned",
        "moving_time_seconds",
    }
)

SLEEP_FIELDS: frozenset[str] = frozenset()

HEALTH_SCORES: frozenset[HealthScoreCategory] = frozenset()
