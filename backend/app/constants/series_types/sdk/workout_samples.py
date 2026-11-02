from app.schemas.enums import SeriesType

# workouts[].samples[].type → SeriesType. Samsung sends these from ExerciseSession `log`;
# Health Connect and HealthKit send no workout samples yet.
WORKOUT_SAMPLE_TYPE_TO_SERIES_TYPE: dict[str, SeriesType] = {
    "heartRate": SeriesType.heart_rate,
    "speed": SeriesType.speed,
    "cadence": SeriesType.cadence,
    "power": SeriesType.power,
}

# Units each sample type is stored in as sent (lowercase). A sample with another unit is
# skipped rather than written into a series with the wrong scale. Cadence is steps per
# minute for running and revolutions per minute for cycling, the same series either way.
WORKOUT_SAMPLE_UNITS: dict[str, frozenset[str]] = {
    "heartRate": frozenset({"bpm", "count/min"}),
    "speed": frozenset({"m/s"}),
    "cadence": frozenset({"spm", "rpm"}),
    "power": frozenset({"w"}),
}

# workouts[].route[] field → SeriesType, same series the cloud providers write GPS tracks to.
WORKOUT_ROUTE_FIELD_TO_SERIES_TYPE: dict[str, SeriesType] = {
    "latitude": SeriesType.latitude,
    "longitude": SeriesType.longitude,
    "altitude_m": SeriesType.elevation,
}

WORKOUT_ROUTE_SERIES: frozenset[SeriesType] = frozenset(WORKOUT_ROUTE_FIELD_TO_SERIES_TYPE.values())


def get_series_type_from_workout_sample_type(workout_sample_type: str) -> SeriesType | None:
    """
    Map an SDK workout sample type to the unified SeriesType enum.
    Returns None when the sample type is not supported.
    """
    return WORKOUT_SAMPLE_TYPE_TO_SERIES_TYPE.get(workout_sample_type)
