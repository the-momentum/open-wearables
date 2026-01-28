from enum import IntEnum

from app.schemas.series_types import SeriesType

METRIC_TYPE_TO_SERIES_TYPE: dict[str, SeriesType] = {
    # =========================================================================
    # Heart & Cardiovascular
    # =========================================================================
    "HKQuantityTypeIdentifierHeartRate": SeriesType.heart_rate,
    "HKQuantityTypeIdentifierRestingHeartRate": SeriesType.resting_heart_rate,
    "HKQuantityTypeIdentifierHeartRateVariabilitySDNN": SeriesType.heart_rate_variability_sdnn,
    "HKQuantityTypeIdentifierHeartRateRecoveryOneMinute": SeriesType.heart_rate_recovery_one_minute,
    "HKQuantityTypeIdentifierWalkingHeartRateAverage": SeriesType.walking_heart_rate_average,
    # =========================================================================
    # Blood & Respiratory
    # =========================================================================
    "HKQuantityTypeIdentifierOxygenSaturation": SeriesType.oxygen_saturation,
    "HKQuantityTypeIdentifierBloodGlucose": SeriesType.blood_glucose,
    "HKQuantityTypeIdentifierBloodPressureSystolic": SeriesType.blood_pressure_systolic,
    "HKQuantityTypeIdentifierBloodPressureDiastolic": SeriesType.blood_pressure_diastolic,
    "HKQuantityTypeIdentifierRespiratoryRate": SeriesType.respiratory_rate,
    # =========================================================================
    # Body Composition
    # =========================================================================
    "HKQuantityTypeIdentifierHeight": SeriesType.height,
    "HKQuantityTypeIdentifierBodyMass": SeriesType.weight,
    "HKQuantityTypeIdentifierBodyFatPercentage": SeriesType.body_fat_percentage,
    "HKQuantityTypeIdentifierBodyMassIndex": SeriesType.body_mass_index,
    "HKQuantityTypeIdentifierLeanBodyMass": SeriesType.lean_body_mass,
    "HKQuantityTypeIdentifierBodyTemperature": SeriesType.body_temperature,
    # =========================================================================
    # Fitness Metrics
    # =========================================================================
    "HKQuantityTypeIdentifierVO2Max": SeriesType.vo2_max,
    "HKQuantityTypeIdentifierSixMinuteWalkTestDistance": SeriesType.six_minute_walk_test_distance,
    # =========================================================================
    # Activity - Basic
    # =========================================================================
    "HKQuantityTypeIdentifierStepCount": SeriesType.steps,
    "HKQuantityTypeIdentifierActiveEnergyBurned": SeriesType.energy,
    "HKQuantityTypeIdentifierBasalEnergyBurned": SeriesType.basal_energy,
    "HKQuantityTypeIdentifierAppleStandTime": SeriesType.stand_time,
    "HKQuantityTypeIdentifierAppleExerciseTime": SeriesType.exercise_time,
    "HKQuantityTypeIdentifierFlightsClimbed": SeriesType.flights_climbed,
    # =========================================================================
    # Activity - Distance
    # =========================================================================
    "HKQuantityTypeIdentifierDistanceWalkingRunning": SeriesType.distance_walking_running,
    "HKQuantityTypeIdentifierDistanceCycling": SeriesType.distance_cycling,
    "HKQuantityTypeIdentifierDistanceSwimming": SeriesType.distance_swimming,
    "HKQuantityTypeIdentifierDistanceDownhillSnowSports": SeriesType.distance_downhill_snow_sports,
    # =========================================================================
    # Walking Metrics
    # =========================================================================
    "HKQuantityTypeIdentifierWalkingStepLength": SeriesType.walking_step_length,
    "HKQuantityTypeIdentifierWalkingSpeed": SeriesType.walking_speed,
    "HKQuantityTypeIdentifierWalkingDoubleSupportPercentage": SeriesType.walking_double_support_percentage,
    "HKQuantityTypeIdentifierWalkingAsymmetryPercentage": SeriesType.walking_asymmetry_percentage,
    "HKQuantityTypeIdentifierAppleWalkingSteadiness": SeriesType.walking_steadiness,
    "HKQuantityTypeIdentifierStairDescentSpeed": SeriesType.stair_descent_speed,
    "HKQuantityTypeIdentifierStairAscentSpeed": SeriesType.stair_ascent_speed,
    # =========================================================================
    # Running Metrics
    # =========================================================================
    "HKQuantityTypeIdentifierRunningPower": SeriesType.running_power,
    "HKQuantityTypeIdentifierRunningSpeed": SeriesType.running_speed,
    "HKQuantityTypeIdentifierRunningVerticalOscillation": SeriesType.running_vertical_oscillation,
    "HKQuantityTypeIdentifierRunningGroundContactTime": SeriesType.running_ground_contact_time,
    "HKQuantityTypeIdentifierRunningStrideLength": SeriesType.running_stride_length,
    # =========================================================================
    # Swimming Metrics
    # =========================================================================
    "HKQuantityTypeIdentifierSwimmingStrokeCount": SeriesType.swimming_stroke_count,
    # =========================================================================
    # Environmental
    # =========================================================================
    "HKQuantityTypeIdentifierEnvironmentalAudioExposure": SeriesType.environmental_audio_exposure,
    "HKQuantityTypeIdentifierHeadphoneAudioExposure": SeriesType.headphone_audio_exposure,
}

HEALTHION_TYPE_TO_SERIES_TYPE: dict[str, SeriesType] = {
    "totalEnergyBurned": SeriesType.energy,
    "totalCalories": SeriesType.energy,
    "totalDistance": SeriesType.distance_walking_running,
    "totalSteps": SeriesType.steps,
}

# =========================================================================
# Category Types
# =========================================================================
# Apple HealthKit category type identifiers (HKCategoryTypeIdentifier...)
# These are used for categorical data like sleep analysis
CATEGORY_TYPE_IDENTIFIERS: set[str] = {
    "HKCategoryTypeIdentifierSleepAnalysis",
}


class SleepPhase(IntEnum):
    IN_BED = 0
    ASLEEP_UNSPECIFIED = 1
    AWAKE = 2
    ASLEEP_CORE = 3
    ASLEEP_DEEP = 4
    ASLEEP_REM = 5


def get_series_type_from_metric_type(metric_type: str) -> SeriesType | None:
    """
    Map a HealthKit metric type identifier to the unified SeriesType enum.
    Returns None when the metric type is not supported.
    """
    return METRIC_TYPE_TO_SERIES_TYPE.get(metric_type)


def get_series_type_from_healthion_type(healthion_type: str) -> SeriesType | None:
    """
    Map a HealthKit metric type identifier to the unified SeriesType enum.
    Returns None when the metric type is not supported.
    """
    return HEALTHION_TYPE_TO_SERIES_TYPE.get(healthion_type)


def get_apple_sleep_phase(apple_sleep_phase: int) -> SleepPhase | None:
    try:
        return SleepPhase(apple_sleep_phase)
    except ValueError:
        return None
