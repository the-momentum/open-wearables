from enum import StrEnum

from app.schemas.series_types import SeriesType


class WorkoutStatisticType(StrEnum):
    """Apple HealthKit workout statistic types.

    These represent the different metrics that can be recorded during a workout session.
    """

    # Duration & Energy
    DURATION = "duration"
    ACTIVE_ENERGY_BURNED = "activeEnergyBurned"
    BASAL_ENERGY_BURNED = "basalEnergyBurned"

    # Distance & Movement
    DISTANCE = "distance"
    STEP_COUNT = "stepCount"
    SWIMMING_STROKE_COUNT = "swimmingStrokeCount"

    # Heart Rate
    MIN_HEART_RATE = "minHeartRate"
    AVERAGE_HEART_RATE = "averageHeartRate"
    MAX_HEART_RATE = "maxHeartRate"

    # Running Metrics
    AVERAGE_RUNNING_POWER = "averageRunningPower"
    AVERAGE_RUNNING_SPEED = "averageRunningSpeed"
    AVERAGE_RUNNING_STRIDE_LENGTH = "averageRunningStrideLength"
    AVERAGE_VERTICAL_OSCILLATION = "averageVerticalOscillation"
    AVERAGE_GROUND_CONTACT_TIME = "averageGroundContactTime"

    # Elevation
    ELEVATION_ASCENDED = "elevationAscended"
    ELEVATION_DESCENDED = "elevationDescended"

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
    # Heart Rate
    "minHeartRate": "heart_rate_min",
    "averageHeartRate": "heart_rate_avg",
    "maxHeartRate": "heart_rate_max",
    # Running Metrics
    "averageRunningPower": "average_watts",
    "averageRunningSpeed": "average_speed",
    # Elevation
    "elevationAscended": "total_elevation_gain",
    # elevationDescended: not stored
    # Speed
    "averageSpeed": "average_speed",
    "maxSpeed": "max_speed",
}


WORKOUT_STATISTIC_TYPE_TO_SERIES_TYPE: dict[str, SeriesType] = {
    # Running Metrics
    "averageRunningStrideLength": SeriesType.running_stride_length,
    "averageVerticalOscillation": SeriesType.running_vertical_oscillation,
    "averageGroundContactTime": SeriesType.running_ground_contact_time,
    # Other Metrics
    "averageMETs": SeriesType.physical_effort,
    "lapLength": SeriesType.distance_other,
    "swimmingLocationType": SeriesType.distance_other,
    "indoorWorkout": SeriesType.physical_effort,
    # Weather
    "weatherTemperature": SeriesType.water_temperature,
    "weatherHumidity": SeriesType.environmental_sound_reduction,
    # Swimming specific
    "swimmingStrokeCount": SeriesType.swimming_stroke_count,
    # Legacy mappings
    "totalEnergyBurned": SeriesType.energy,
    "totalCalories": SeriesType.energy,
    "totalDistance": SeriesType.distance_walking_running,
    "totalSteps": SeriesType.steps,
}


def get_detail_field_from_workout_statistic_type(workout_statistic_type: str) -> str | None:
    """
    Map a HealthKit workout statistic type identifier to the EventRecordDetail field name.
    Returns None when the metric type is not supported.
    """
    return WORKOUT_STATISTIC_TYPE_TO_DETAIL_FIELD.get(workout_statistic_type)


def get_series_type_from_workout_statistic_type(workout_statistic_type: str) -> SeriesType | None:
    """
    Map a HealthKit metric type identifier to the unified SeriesType enum.
    Returns None when the metric type is not supported.
    """
    return WORKOUT_STATISTIC_TYPE_TO_SERIES_TYPE.get(workout_statistic_type)
