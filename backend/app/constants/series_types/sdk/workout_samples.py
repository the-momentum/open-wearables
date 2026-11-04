from app.schemas.enums import SeriesType

# workouts[].samples[].type → SeriesType and the units it is stored in as sent (lowercase). A sample
# with another unit is skipped rather than written into a series with the wrong scale. Samsung sends
# these from ExerciseSession `log`; Health Connect and HealthKit send no workout samples yet.
# Cadence is steps per minute for running and revolutions per minute for cycling, the same series.
WORKOUT_SAMPLE_TYPES: dict[str, tuple[SeriesType, frozenset[str]]] = {
    "heartRate": (SeriesType.heart_rate, frozenset({"bpm", "count/min"})),
    "speed": (SeriesType.speed, frozenset({"m/s"})),
    "cadence": (SeriesType.cadence, frozenset({"spm", "rpm"})),
    "power": (SeriesType.power, frozenset({"w"})),
}

WORKOUT_SAMPLE_SERIES: frozenset[SeriesType] = frozenset(series for series, _ in WORKOUT_SAMPLE_TYPES.values())

# workouts[].route[] key → SeriesType, same series the cloud providers write GPS tracks to.
WORKOUT_ROUTE_FIELD_TO_SERIES_TYPE: dict[str, SeriesType] = {
    "latitude": SeriesType.latitude,
    "longitude": SeriesType.longitude,
    "altitudeM": SeriesType.elevation,
}

WORKOUT_ROUTE_SERIES: frozenset[SeriesType] = frozenset(WORKOUT_ROUTE_FIELD_TO_SERIES_TYPE.values())
