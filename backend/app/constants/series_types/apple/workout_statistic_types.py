from app.schemas.series_types import SeriesType


WORKOUT_STATISTIC_TYPE_TO_SERIES_TYPE: dict[str, SeriesType] = {
    "totalEnergyBurned": SeriesType.energy,
    "totalCalories": SeriesType.energy,
    "totalDistance": SeriesType.distance_walking_running,
    "totalSteps": SeriesType.steps,
}


def get_series_type_from_workout_statistic_type(workout_statistic_type: str) -> SeriesType | None:
    """
    Map a HealthKit metric type identifier to the unified SeriesType enum.
    Returns None when the metric type is not supported.
    """
    return WORKOUT_STATISTIC_TYPE_TO_SERIES_TYPE.get(workout_statistic_type)


