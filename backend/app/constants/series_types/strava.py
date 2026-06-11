from app.schemas.enums import SeriesType

# Strava activity stream keys
# (https://developers.strava.com/docs/reference/#api-Streams) mapped to the
# unified SeriesType. The "time" stream is the per-sample offset axis and is
# handled separately, so it is intentionally excluded here.
STREAM_KEY_SERIES_TYPE: dict[str, SeriesType] = {
    "heartrate": SeriesType.heart_rate,
    "velocity_smooth": SeriesType.speed,
    "cadence": SeriesType.cadence,
    "watts": SeriesType.power,
}

# Value for the Strava streams `keys` query param: the time axis first, then
# every metric stream we ingest.
STREAM_KEYS_PARAM: str = ",".join(["time", *STREAM_KEY_SERIES_TYPE])
