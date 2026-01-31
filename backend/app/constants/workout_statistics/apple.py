from enum import StrEnum


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
