from enum import IntEnum, StrEnum

from app.schemas.series_types import SeriesType


class AppleMetricType(StrEnum):
    """Apple HealthKit quantity type identifiers (HKQuantityTypeIdentifier...).

    These represent the different health metrics that can be recorded by HealthKit.
    """

    # Heart & Cardiovascular
    HEART_RATE = "HKQuantityTypeIdentifierHeartRate"
    RESTING_HEART_RATE = "HKQuantityTypeIdentifierRestingHeartRate"
    HEART_RATE_VARIABILITY_SDNN = "HKQuantityTypeIdentifierHeartRateVariabilitySDNN"
    HEART_RATE_RECOVERY_ONE_MINUTE = "HKQuantityTypeIdentifierHeartRateRecoveryOneMinute"
    WALKING_HEART_RATE_AVERAGE = "HKQuantityTypeIdentifierWalkingHeartRateAverage"

    # Blood & Respiratory
    OXYGEN_SATURATION = "HKQuantityTypeIdentifierOxygenSaturation"
    BLOOD_GLUCOSE = "HKQuantityTypeIdentifierBloodGlucose"
    BLOOD_PRESSURE_SYSTOLIC = "HKQuantityTypeIdentifierBloodPressureSystolic"
    BLOOD_PRESSURE_DIASTOLIC = "HKQuantityTypeIdentifierBloodPressureDiastolic"
    RESPIRATORY_RATE = "HKQuantityTypeIdentifierRespiratoryRate"

    # Body Composition
    HEIGHT = "HKQuantityTypeIdentifierHeight"
    BODY_MASS = "HKQuantityTypeIdentifierBodyMass"
    BODY_FAT_PERCENTAGE = "HKQuantityTypeIdentifierBodyFatPercentage"
    BODY_MASS_INDEX = "HKQuantityTypeIdentifierBodyMassIndex"
    LEAN_BODY_MASS = "HKQuantityTypeIdentifierLeanBodyMass"
    BODY_TEMPERATURE = "HKQuantityTypeIdentifierBodyTemperature"

    # Fitness Metrics
    VO2_MAX = "HKQuantityTypeIdentifierVO2Max"
    SIX_MINUTE_WALK_TEST_DISTANCE = "HKQuantityTypeIdentifierSixMinuteWalkTestDistance"

    # Activity - Basic
    STEP_COUNT = "HKQuantityTypeIdentifierStepCount"
    ACTIVE_ENERGY_BURNED = "HKQuantityTypeIdentifierActiveEnergyBurned"
    BASAL_ENERGY_BURNED = "HKQuantityTypeIdentifierBasalEnergyBurned"
    APPLE_STAND_TIME = "HKQuantityTypeIdentifierAppleStandTime"
    APPLE_EXERCISE_TIME = "HKQuantityTypeIdentifierAppleExerciseTime"
    FLIGHTS_CLIMBED = "HKQuantityTypeIdentifierFlightsClimbed"

    # Activity - Distance
    DISTANCE_WALKING_RUNNING = "HKQuantityTypeIdentifierDistanceWalkingRunning"
    DISTANCE_CYCLING = "HKQuantityTypeIdentifierDistanceCycling"
    DISTANCE_SWIMMING = "HKQuantityTypeIdentifierDistanceSwimming"
    DISTANCE_DOWNHILL_SNOW_SPORTS = "HKQuantityTypeIdentifierDistanceDownhillSnowSports"
    DISTANCE_PADDLE_SPORTS = "HKQuantityTypeIdentifierDistancePaddleSports"
    DISTANCE_ROWING = "HKQuantityTypeIdentifierDistanceRowing"
    DISTANCE_SKATING_SPORTS = "HKQuantityTypeIdentifierDistanceSkatingSports"
    DISTANCE_WHEELCHAIR = "HKQuantityTypeIdentifierDistanceWheelchair"
    DISTANCE_CROSS_COUNTRY_SKIING = "HKQuantityTypeIdentifierDistanceCrossCountrySkiing"

    # Walking Metrics
    WALKING_STEP_LENGTH = "HKQuantityTypeIdentifierWalkingStepLength"
    WALKING_SPEED = "HKQuantityTypeIdentifierWalkingSpeed"
    WALKING_DOUBLE_SUPPORT_PERCENTAGE = "HKQuantityTypeIdentifierWalkingDoubleSupportPercentage"
    WALKING_ASYMMETRY_PERCENTAGE = "HKQuantityTypeIdentifierWalkingAsymmetryPercentage"
    APPLE_WALKING_STEADINESS = "HKQuantityTypeIdentifierAppleWalkingSteadiness"
    STAIR_DESCENT_SPEED = "HKQuantityTypeIdentifierStairDescentSpeed"
    STAIR_ASCENT_SPEED = "HKQuantityTypeIdentifierStairAscentSpeed"

    # Running Metrics
    RUNNING_POWER = "HKQuantityTypeIdentifierRunningPower"
    RUNNING_SPEED = "HKQuantityTypeIdentifierRunningSpeed"
    RUNNING_VERTICAL_OSCILLATION = "HKQuantityTypeIdentifierRunningVerticalOscillation"
    RUNNING_GROUND_CONTACT_TIME = "HKQuantityTypeIdentifierRunningGroundContactTime"
    RUNNING_STRIDE_LENGTH = "HKQuantityTypeIdentifierRunningStrideLength"

    # Swimming Metrics
    SWIMMING_STROKE_COUNT = "HKQuantityTypeIdentifierSwimmingStrokeCount"

    # Environmental
    ENVIRONMENTAL_AUDIO_EXPOSURE = "HKQuantityTypeIdentifierEnvironmentalAudioExposure"
    HEADPHONE_AUDIO_EXPOSURE = "HKQuantityTypeIdentifierHeadphoneAudioExposure"
    ENVIRONMENTAL_SOUND_REDUCTION = "HKQuantityTypeIdentifierEnvironmentalSoundReduction"
    TIME_IN_DAYLIGHT = "HKQuantityTypeIdentifierTimeInDaylight"

    # Workout Metrics
    PHYSICAL_EFFORT = "HKQuantityTypeIdentifierPhysicalEffort"
    WORKOUT_EFFORT_SCORE = "HKQuantityTypeIdentifierWorkoutEffortScore"
    ESTIMATED_WORKOUT_EFFORT_SCORE = "HKQuantityTypeIdentifierEstimatedWorkoutEffortScore"

    # Apple-specific Activity Metrics
    APPLE_MOVE_TIME = "HKQuantityTypeIdentifierAppleMoveTime"
    APPLE_SLEEPING_WRIST_TEMPERATURE = "HKQuantityTypeIdentifierAppleSleepingWristTemperature"

    # Blood & Respiratory - Extended
    BLOOD_ALCOHOL_CONTENT = "HKQuantityTypeIdentifierBloodAlcoholContent"
    PERIPHERAL_PERFUSION_INDEX = "HKQuantityTypeIdentifierPeripheralPerfusionIndex"
    FORCED_VITAL_CAPACITY = "HKQuantityTypeIdentifierForcedVitalCapacity"
    FORCED_EXPIRATORY_VOLUME_1 = "HKQuantityTypeIdentifierForcedExpiratoryVolume1"
    PEAK_EXPIRATORY_FLOW_RATE = "HKQuantityTypeIdentifierPeakExpiratoryFlowRate"
    BASAL_BODY_TEMPERATURE = "HKQuantityTypeIdentifierBasalBodyTemperature"
    SLEEPING_BREATHING_DISTURBANCES = "HKQuantityTypeIdentifierAppleSleepingBreathingDisturbances"

    # Body Metrics - Extended
    WAIST_CIRCUMFERENCE = "HKQuantityTypeIdentifierWaistCircumference"
    INSULIN_DELIVERY = "HKQuantityTypeIdentifierInsulinDelivery"

    # Behavioral
    NUMBER_OF_TIMES_FALLEN = "HKQuantityTypeIdentifierNumberOfTimesFallen"
    INHALER_USAGE = "HKQuantityTypeIdentifierInhalerUsage"
    NUMBER_OF_ALCOHOLIC_BEVERAGES = "HKQuantityTypeIdentifierNumberOfAlcoholicBeverages"

    # Electrodermal
    ELECTRODERMAL_ACTIVITY = "HKQuantityTypeIdentifierElectrodermalActivity"

    # Ultraviolet Exposure
    UV_EXPOSURE = "HKQuantityTypeIdentifierUVExposure"

    # Wheelchair Metrics
    PUSH_COUNT = "HKQuantityTypeIdentifierPushCount"

    # Atrial Fibrillation
    ATRIAL_FIBRILLATION_BURDEN = "HKQuantityTypeIdentifierAtrialFibrillationBurden"

    # Water/Diving Metrics
    UNDERWATER_DEPTH = "HKQuantityTypeIdentifierUnderwaterDepth"
    WATER_TEMPERATURE = "HKQuantityTypeIdentifierWaterTemperature"

    # Cycling Metrics
    CYCLING_CADENCE = "HKQuantityTypeIdentifierCyclingCadence"
    CYCLING_FUNCTIONAL_THRESHOLD_POWER = "HKQuantityTypeIdentifierCyclingFunctionalThresholdPower"
    CYCLING_POWER = "HKQuantityTypeIdentifierCyclingPower"
    CYCLING_SPEED = "HKQuantityTypeIdentifierCyclingSpeed"

    # Winter/Snow Sports
    CROSS_COUNTRY_SKIING_SPEED = "HKQuantityTypeIdentifierCrossCountrySkiingSpeed"

    # Water Sports
    PADDLE_SPORTS_SPEED = "HKQuantityTypeIdentifierPaddleSportsSpeed"
    ROWING_SPEED = "HKQuantityTypeIdentifierRowingSpeed"

    # Nike Fuel (deprecated but included for backwards compatibility)
    NIKE_FUEL = "HKQuantityTypeIdentifierNikeFuel"


class AppleCategoryType(StrEnum):
    """Apple HealthKit category type identifiers (HKCategoryTypeIdentifier...).

    These represent categorical health data like sleep analysis.
    """

    SLEEP_ANALYSIS = "HKCategoryTypeIdentifierSleepAnalysis"


METRIC_TYPE_TO_SERIES_TYPE: dict[AppleMetricType, SeriesType] = {
    # Heart & Cardiovascular
    AppleMetricType.HEART_RATE: SeriesType.heart_rate,
    AppleMetricType.RESTING_HEART_RATE: SeriesType.resting_heart_rate,
    AppleMetricType.HEART_RATE_VARIABILITY_SDNN: SeriesType.heart_rate_variability_sdnn,
    AppleMetricType.HEART_RATE_RECOVERY_ONE_MINUTE: SeriesType.heart_rate_recovery_one_minute,
    AppleMetricType.WALKING_HEART_RATE_AVERAGE: SeriesType.walking_heart_rate_average,
    # Blood & Respiratory
    AppleMetricType.OXYGEN_SATURATION: SeriesType.oxygen_saturation,
    AppleMetricType.BLOOD_GLUCOSE: SeriesType.blood_glucose,
    AppleMetricType.BLOOD_PRESSURE_SYSTOLIC: SeriesType.blood_pressure_systolic,
    AppleMetricType.BLOOD_PRESSURE_DIASTOLIC: SeriesType.blood_pressure_diastolic,
    AppleMetricType.RESPIRATORY_RATE: SeriesType.respiratory_rate,
    AppleMetricType.BASAL_BODY_TEMPERATURE: SeriesType.body_temperature,
    AppleMetricType.SLEEPING_BREATHING_DISTURBANCES: SeriesType.sleeping_breathing_disturbances,
    # Blood & Respiratory - Extended (no corresponding metric type)
    # BLOOD_ALCOHOL_CONTENT
    # PERIPHERAL_PERFUSION_INDEX
    # FORCED_VITAL_CAPACITY
    # FORCED_EXPIRATORY_VOLUME_1
    # PEAK_EXPIRATORY_FLOW_RATE
    # Body Composition
    AppleMetricType.HEIGHT: SeriesType.height,
    AppleMetricType.BODY_MASS: SeriesType.weight,
    AppleMetricType.BODY_FAT_PERCENTAGE: SeriesType.body_fat_percentage,
    AppleMetricType.BODY_MASS_INDEX: SeriesType.body_mass_index,
    AppleMetricType.LEAN_BODY_MASS: SeriesType.lean_body_mass,
    AppleMetricType.BODY_TEMPERATURE: SeriesType.body_temperature,
    # Body Composition - Extended (no corresponding metric type)
    # WAIST_CIRCUMFERENCE
    # Fitness Metrics
    AppleMetricType.VO2_MAX: SeriesType.vo2_max,
    AppleMetricType.SIX_MINUTE_WALK_TEST_DISTANCE: SeriesType.six_minute_walk_test_distance,
    # Activity - Basic
    AppleMetricType.STEP_COUNT: SeriesType.steps,
    AppleMetricType.ACTIVE_ENERGY_BURNED: SeriesType.energy,
    AppleMetricType.BASAL_ENERGY_BURNED: SeriesType.basal_energy,
    AppleMetricType.APPLE_STAND_TIME: SeriesType.stand_time,
    AppleMetricType.APPLE_EXERCISE_TIME: SeriesType.exercise_time,
    AppleMetricType.FLIGHTS_CLIMBED: SeriesType.flights_climbed,
    AppleMetricType.PHYSICAL_EFFORT: SeriesType.physical_effort,
    AppleMetricType.APPLE_MOVE_TIME: SeriesType.exercise_time,
    # Activity - Distance
    AppleMetricType.DISTANCE_WALKING_RUNNING: SeriesType.distance_walking_running,
    AppleMetricType.DISTANCE_CYCLING: SeriesType.distance_cycling,
    AppleMetricType.DISTANCE_SWIMMING: SeriesType.distance_swimming,
    AppleMetricType.DISTANCE_DOWNHILL_SNOW_SPORTS: SeriesType.distance_downhill_snow_sports,
    # Activity - Distance - Extended (no corresponding metric type)
    AppleMetricType.DISTANCE_WHEELCHAIR: SeriesType.distance_other,
    AppleMetricType.DISTANCE_CROSS_COUNTRY_SKIING: SeriesType.distance_other,
    AppleMetricType.DISTANCE_PADDLE_SPORTS: SeriesType.distance_other,
    AppleMetricType.DISTANCE_ROWING: SeriesType.distance_other,
    AppleMetricType.DISTANCE_SKATING_SPORTS: SeriesType.distance_other,
    # Walking Metrics
    AppleMetricType.WALKING_STEP_LENGTH: SeriesType.walking_step_length,
    AppleMetricType.WALKING_SPEED: SeriesType.walking_speed,
    AppleMetricType.WALKING_DOUBLE_SUPPORT_PERCENTAGE: SeriesType.walking_double_support_percentage,
    AppleMetricType.WALKING_ASYMMETRY_PERCENTAGE: SeriesType.walking_asymmetry_percentage,
    AppleMetricType.APPLE_WALKING_STEADINESS: SeriesType.walking_steadiness,
    AppleMetricType.STAIR_DESCENT_SPEED: SeriesType.stair_descent_speed,
    AppleMetricType.STAIR_ASCENT_SPEED: SeriesType.stair_ascent_speed,
    # Running Metrics
    AppleMetricType.RUNNING_POWER: SeriesType.running_power,
    AppleMetricType.RUNNING_SPEED: SeriesType.running_speed,
    AppleMetricType.RUNNING_VERTICAL_OSCILLATION: SeriesType.running_vertical_oscillation,
    AppleMetricType.RUNNING_GROUND_CONTACT_TIME: SeriesType.running_ground_contact_time,
    AppleMetricType.RUNNING_STRIDE_LENGTH: SeriesType.running_stride_length,
    # Swimming Metrics
    AppleMetricType.SWIMMING_STROKE_COUNT: SeriesType.swimming_stroke_count,
    # Cycling Metrics
    AppleMetricType.CYCLING_CADENCE: SeriesType.cadence,
    AppleMetricType.CYCLING_POWER: SeriesType.power,
    AppleMetricType.CYCLING_FUNCTIONAL_THRESHOLD_POWER: SeriesType.power,
    # Cycling Metrics - Extended (no corresponding metric type)
    # CYCLING_SPEED
    # Environmental
    AppleMetricType.ENVIRONMENTAL_AUDIO_EXPOSURE: SeriesType.environmental_audio_exposure,
    AppleMetricType.HEADPHONE_AUDIO_EXPOSURE: SeriesType.headphone_audio_exposure,
    AppleMetricType.ENVIRONMENTAL_SOUND_REDUCTION: SeriesType.environmental_sound_reduction,
    AppleMetricType.TIME_IN_DAYLIGHT: SeriesType.time_in_daylight,
    AppleMetricType.WATER_TEMPERATURE: SeriesType.water_temperature,
    # Environmental - Extended (no corresponding metric type)
    # UNDERWATER_DEPTH
    # Behavioral (no corresponding metric type)
    # NUMBER_OF_TIMES_FALLEN
    # INHALER_USAGE
    # NUMBER_OF_ALCOHOLIC_BEVERAGES
    # Electrodermal (no corresponding metric type)
    # ELECTRODERMAL_ACTIVITY
    # Ultraviolet Exposure (no corresponding metric type)
    # UV_EXPOSURE
    # Wheelchair Metrics (no corresponding metric type)
    # PUSH_COUNT
    # Apple-specific Temperature
    AppleMetricType.APPLE_SLEEPING_WRIST_TEMPERATURE: SeriesType.body_temperature,
    # Atrial Fibrillation (no corresponding metric type)
    # ATRIAL_FIBRILLATION_BURDEN
    # Workout Metrics (no corresponding metric type)
    # WORKOUT_EFFORT_SCORE
    # ESTIMATED_WORKOUT_EFFORT_SCORE
    # Winter/Snow Sports (no corresponding metric type)
    # CROSS_COUNTRY_SKIING_SPEED
    # Other Sports (no corresponding metric type)
    # PADDLE_SPORTS_SPEED
    # ROWING_SPEED
    # Nike Fuel (deprecated, no corresponding metric type)
    # NIKE_FUEL
    # Insulin & Other (no corresponding metric type)
    # INSULIN_DELIVERY
}

HEALTHION_TYPE_TO_SERIES_TYPE: dict[str, SeriesType] = {
    "totalEnergyBurned": SeriesType.energy,
    "totalCalories": SeriesType.energy,
    "totalDistance": SeriesType.distance_walking_running,
    "totalSteps": SeriesType.steps,
}

# Category types set (for backwards compatibility and validation)
CATEGORY_TYPE_IDENTIFIERS: set[AppleCategoryType] = {
    AppleCategoryType.SLEEP_ANALYSIS,
}


class SleepPhase(IntEnum):
    IN_BED = 0
    ASLEEP_UNSPECIFIED = 1
    AWAKE = 2
    ASLEEP_CORE = 3
    ASLEEP_DEEP = 4
    ASLEEP_REM = 5


def get_series_type_from_metric_type(metric_type: AppleMetricType | str) -> SeriesType | None:
    """
    Map a HealthKit metric type identifier to the unified SeriesType enum.
    Returns None when the metric type is not supported.
    """
    return METRIC_TYPE_TO_SERIES_TYPE.get(metric_type)  # type: ignore[arg-type]


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
