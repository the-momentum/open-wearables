from enum import StrEnum

from app.schemas.enums import SeriesType
from app.schemas.model_crud.activities import StatColumn


class WorkoutStatisticType(StrEnum):
    """Apple HealthKit workout statistic types.

    These represent the different metrics that can be recorded during a workout session.
    """

    # Duration & Energy
    DURATION = "duration"
    TOTAL_DURATION = "totalDuration"
    ACTIVE_ENERGY_BURNED = "activeEnergyBurned"
    BASAL_ENERGY_BURNED = "basalEnergyBurned"
    CALORIES = "calories"
    TOTAL_CALORIES = "totalCalories"

    # Distance & Movement
    DISTANCE = "distance"
    STEP_COUNT = "stepCount"
    SWIMMING_STROKE_COUNT = "swimmingStrokeCount"

    # Heart Rate
    MIN_HEART_RATE = "minHeartRate"
    AVERAGE_HEART_RATE = "averageHeartRate"
    MAX_HEART_RATE = "maxHeartRate"
    MEAN_HEART_RATE = "meanHeartRate"

    # Running Metrics
    MEAN_SPEED = "meanSpeed"
    MEAN_CADENCE = "meanCadence"
    MAX_CADENCE = "maxCadence"
    AVERAGE_RUNNING_POWER = "averageRunningPower"
    AVERAGE_RUNNING_SPEED = "averageRunningSpeed"
    AVERAGE_RUNNING_STRIDE_LENGTH = "averageRunningStrideLength"
    AVERAGE_VERTICAL_OSCILLATION = "averageVerticalOscillation"
    AVERAGE_GROUND_CONTACT_TIME = "averageGroundContactTime"
    VO2_MAX = "vo2Max"

    # Cycling Metrics (Apple, iOS 17+)
    AVERAGE_CYCLING_POWER = "averageCyclingPower"
    AVERAGE_CYCLING_CADENCE = "averageCyclingCadence"
    AVERAGE_CYCLING_SPEED = "averageCyclingSpeed"

    # Power & Pedaling (Samsung)
    MEAN_POWER = "meanPower"
    MAX_POWER = "maxPower"
    MEAN_RPM = "meanRpm"

    # Elevation
    ELEVATION_ASCENDED = "elevationAscended"
    ELEVATION_DESCENDED = "elevationDescended"
    ALTITUDE_GAIN = "altitudeGain"
    ALTITUDE_LOSS = "altitudeLoss"
    MAX_ALTITUDE = "maxAltitude"
    MIN_ALTITUDE = "minAltitude"

    # Speed
    AVERAGE_SPEED = "averageSpeed"
    MAX_SPEED = "maxSpeed"

    # Other Metrics
    AVERAGE_METS = "averageMETs"
    LAP_LENGTH = "lapLength"
    SWIMMING_LOCATION_TYPE = "swimmingLocationType"
    INDOOR_WORKOUT = "indoorWorkout"

    # Weather
    WEATHER_TEMPERATURE = "weatherTemperature"
    WEATHER_HUMIDITY = "weatherHumidity"


# Mapping from workout statistic type to EventRecordMetrics field name
# Only includes stats that:
# 1. Are NOT in WORKOUT_STATISTIC_TYPE_TO_SERIES_TYPE (below)
# 2. Are NOT handled separately (like duration, activeEnergyBurned, basalEnergyBurned)
WORKOUT_STATISTIC_TYPE_TO_DETAIL_FIELD: dict[str, str] = {
    # Distance & Movement
    "distance": "distance",
    "stepCount": "steps_count",
    # Heart Rate (Apple)
    "minHeartRate": "heart_rate_min",
    "averageHeartRate": "heart_rate_avg",
    "maxHeartRate": "heart_rate_max",
    # Heart Rate (Samsung)
    "meanHeartRate": "heart_rate_avg",
    # Running Metrics
    "averageRunningPower": "average_watts",
    "averageRunningSpeed": "average_speed",
    # Cycling Metrics (Apple, iOS 17+)
    "averageCyclingPower": "average_watts",
    "averageCyclingCadence": "average_cadence",
    "averageCyclingSpeed": "average_speed",
    # Power & Pedaling (Samsung)
    "meanPower": "average_watts",
    "maxPower": "max_watts",
    "meanRpm": "average_cadence",
    # Elevation (Apple)
    "elevationAscended": "total_elevation_gain",
    # elevationDescended: not stored
    # Elevation (Samsung)
    "altitudeGain": "total_elevation_gain",
    # altitudeLoss
    "maxAltitude": "elev_high",
    "minAltitude": "elev_low",
    # Speed (Apple + Samsung)
    "averageSpeed": "average_speed",
    "maxSpeed": "max_speed",
    "meanSpeed": "average_speed",
}

# Several stats can fill the same detail field (e.g. a workout carrying both running and
# cycling power). Earlier keys win regardless of payload order; unlisted keys rank last.
# Workout-level averages beat sensor averages, and sport-specific power beats
# `averageRunningPower`, which Health Connect also sends for any workout type.
WORKOUT_DETAIL_FIELD_PRECEDENCE: dict[str, tuple[str, ...]] = {
    "average_watts": ("averageCyclingPower", "meanPower", "averageRunningPower"),
    "average_speed": ("averageSpeed", "meanSpeed", "averageCyclingSpeed", "averageRunningSpeed"),
}


WORKOUT_STATISTIC_TYPE_TO_SERIES_TYPE: dict[str, SeriesType] = {
    # Running Metrics
    "averageRunningStrideLength": SeriesType.running_stride_length,
    "averageVerticalOscillation": SeriesType.running_vertical_oscillation,
    "averageGroundContactTime": SeriesType.running_ground_contact_time,
    # Other Metrics
    "averageMETs": SeriesType.physical_effort,
    # "lapLength": -- unhandled
    # "swimmingLocationType": -- unhandled
    # "indoorWorkout": -- unhandled
    # Weather
    "weatherTemperature": SeriesType.weather_temperature,
    "weatherHumidity": SeriesType.weather_humidity,
    # Swimming specific
    "swimmingStrokeCount": SeriesType.swimming_stroke_count,
    # Samsung / Health Connect
    "meanCadence": SeriesType.cadence,
    "maxCadence": SeriesType.cadence,
    "vo2Max": SeriesType.vo2_max,
    # Legacy mappings
    "totalEnergyBurned": SeriesType.active_energy,
    "totalDistance": SeriesType.distance_walking_running,
    "totalSteps": SeriesType.steps,
}

# Statistics other than their series' own, for event_record_aggregate (max cadence beside the mean).
WORKOUT_STATISTIC_STAT: dict[str, StatColumn] = {"maxCadence": "max"}

# Energy statistics summed into energy_burned -> the series of that sum. Samsung's ``calories`` is absent:
# its docs do not say whether it includes BMR.
WORKOUT_ENERGY_SERIES: dict[frozenset[str], SeriesType] = {
    frozenset({WorkoutStatisticType.ACTIVE_ENERGY_BURNED}): SeriesType.active_energy,
    frozenset({WorkoutStatisticType.BASAL_ENERGY_BURNED}): SeriesType.basal_energy,
    frozenset(
        {WorkoutStatisticType.ACTIVE_ENERGY_BURNED, WorkoutStatisticType.BASAL_ENERGY_BURNED}
    ): SeriesType.total_energy,
    # Health Connect TotalCaloriesBurnedRecord: "including active & basal energy burned (BMR)"
    frozenset({WorkoutStatisticType.TOTAL_CALORIES}): SeriesType.total_energy,
}

# Of the above, only these exist on Samsung's ExerciseSession; the rest are HealthKit-only.
SAMSUNG_WORKOUT_STATISTIC_TYPE_TO_SERIES_TYPE: dict[str, SeriesType] = {
    k: v
    for k, v in WORKOUT_STATISTIC_TYPE_TO_SERIES_TYPE.items()
    if k in {WorkoutStatisticType.MEAN_CADENCE, WorkoutStatisticType.MAX_CADENCE, WorkoutStatisticType.VO2_MAX}
}


def get_detail_field_from_workout_statistic_type(workout_statistic_type: str) -> str | None:
    """
    Map a HealthKit workout statistic type identifier to the EventRecordDetail field name.
    Returns None when the metric type is not supported.
    """
    return WORKOUT_STATISTIC_TYPE_TO_DETAIL_FIELD.get(workout_statistic_type)


def get_detail_field_precedence(detail_field: str, workout_statistic_type: str) -> int:
    """
    Rank of a statistic among the sources of a detail field; lower wins.
    """
    order = WORKOUT_DETAIL_FIELD_PRECEDENCE.get(detail_field, ())
    return order.index(workout_statistic_type) if workout_statistic_type in order else len(order)


def get_series_type_from_workout_statistic_type(workout_statistic_type: str) -> SeriesType | None:
    """
    Map a HealthKit metric type identifier to the unified SeriesType enum.
    Returns None when the metric type is not supported.
    """
    return WORKOUT_STATISTIC_TYPE_TO_SERIES_TYPE.get(workout_statistic_type)
