from app.schemas.time_series import SeriesType

METRIC_TYPE_TO_SERIES_TYPE: dict[str, SeriesType] = {
    "HKQuantityTypeIdentifierHeartRate": SeriesType.heart_rate,
    "HKQuantityTypeIdentifierStepCount": SeriesType.steps,
    "HKQuantityTypeIdentifierActiveEnergyBurned": SeriesType.energy,
    "HKQuantityTypeIdentifierBasalEnergyBurned": SeriesType.energy,
    "HKQuantityTypeIdentifierRespiratoryRate": SeriesType.respiratory_rate,
    "HKQuantityTypeIdentifierWalkingHeartRateAverage": SeriesType.walking_heart_rate_average,
    "HKQuantityTypeIdentifierHeartRateVariabilitySDNN": SeriesType.heart_rate_variability_sdnn,
    "HKQuantityTypeIdentifierOxygenSaturation": SeriesType.oxygen_saturation,
    "HKQuantityTypeIdentifierHeight": SeriesType.height,
    "HKQuantityTypeIdentifierDistanceWalkingRunning": SeriesType.distance_walking_running,
}


def get_series_type_from_metric_type(metric_type: str) -> SeriesType | None:
    """
    Map a HealthKit metric type identifier to the unified SeriesType enum.
    Returns None when the metric type is not supported.
    """
    return METRIC_TYPE_TO_SERIES_TYPE.get(metric_type)