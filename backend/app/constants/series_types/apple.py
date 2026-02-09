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
    """
    Apple HealthKit category type identifiers (HKCategoryTypeIdentifier...).

    These represent categorical health data like sleep analysis.
    """

    SLEEP_ANALYSIS = "HKCategoryTypeIdentifierSleepAnalysis"

    """
    EVENTS
    Values: 0 = nonApplicable, 1 = depends on event type
    """
    HIGH_HEART_RATE_EVENT = "HKCategoryTypeIdentifierHighHeartRateEvent"
    LOW_HEART_RATE_EVENT = "HKCategoryTypeIdentifierLowHeartRateEvent"
    IRREGULAR_HEART_RHYTHM_EVENT = "HKCategoryTypeIdentifierIrregularHeartRhythmEvent"
    HANDWASHING_EVENT = "HKCategoryTypeIdentifierHandwashingEvent"
    APPLE_WALKING_STEADINESS_EVENT = "HKCategoryTypeIdentifierAppleWalkingSteadinessEvent"
    LOW_CARDIO_FITNESS_EVENT = "HKCategoryTypeIdentifierLowCardioFitnessEvent"
    ENVIRONMENTAL_AUDIO_EXPOSURE_EVENT = "HKCategoryTypeIdentifierEnvironmentalAudioExposureEvent"
    HEADPHONE_AUDIO_EXPOSURE_EVENT = "HKCategoryTypeIdentifierHeadphoneAudioExposureEvent"

    """
    TEST RESULTS
    Values: 1 = negative, 2 = positive, 3 = indeterminate
    """
    PREGNANCY_TEST_RESULT = "HKCategoryTypeIdentifierPregnancyTestResult"
    PROGESTERONE_TEST_RESULT = "HKCategoryTypeIdentifierProgesteroneTestResult"

    """
    CONTRACEPTIVE METHODS
    Values: 1 = unspecified, 2 = implant, 3 = injection,
    4 = intrauterineDevice, 5 = intravaginalRing, 6 = oral, 7 = patch
    """
    CONTRACEPTIVE_METHODS = "HKCategoryTypeIdentifierContraceptive"

    """
    LAB RESULTS
    Values: 1 = unspecified, 2 = positive, 3 = negative
    """
    LAB_RESULTS = "HKCategoryTypeIdentifierLabResult"

    """
    LOSS OF SMELL OR TASTE   
    Values: 0 = present, 1 = notPresent
    """
    LOSS_OF_SMELL = "HKCategoryTypeIdentifierLossOfSmell"
    LOSS_OF_TASTE = "HKCategoryTypeIdentifierLossOfTaste"

    """
    APPETITE CHANGE   
    Values: 0 = unspecified, 1 = noChange, 2 = decreased, 3 = increased
    """
    APPETITE_CHANGE = "HKCategoryTypeIdentifierAppetiteChange"



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
    # Blood & Respiratory - Extended
    AppleMetricType.BLOOD_ALCOHOL_CONTENT: SeriesType.blood_alcohol_content,
    AppleMetricType.PERIPHERAL_PERFUSION_INDEX: SeriesType.peripheral_perfusion_index,
    AppleMetricType.FORCED_VITAL_CAPACITY: SeriesType.forced_vital_capacity,
    AppleMetricType.FORCED_EXPIRATORY_VOLUME_1: SeriesType.forced_expiratory_volume_1,
    AppleMetricType.PEAK_EXPIRATORY_FLOW_RATE: SeriesType.peak_expiratory_flow_rate,
    # Body Composition
    AppleMetricType.HEIGHT: SeriesType.height,
    AppleMetricType.BODY_MASS: SeriesType.weight,
    AppleMetricType.BODY_FAT_PERCENTAGE: SeriesType.body_fat_percentage,
    AppleMetricType.BODY_MASS_INDEX: SeriesType.body_mass_index,
    AppleMetricType.LEAN_BODY_MASS: SeriesType.lean_body_mass,
    AppleMetricType.BODY_TEMPERATURE: SeriesType.body_temperature,
    # Body Composition - Extended (no corresponding metric type)
    AppleMetricType.WAIST_CIRCUMFERENCE: SeriesType.waist_circumference,
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
    AppleMetricType.CYCLING_SPEED: SeriesType.speed,
    # Environmental
    AppleMetricType.ENVIRONMENTAL_AUDIO_EXPOSURE: SeriesType.environmental_audio_exposure,
    AppleMetricType.HEADPHONE_AUDIO_EXPOSURE: SeriesType.headphone_audio_exposure,
    AppleMetricType.ENVIRONMENTAL_SOUND_REDUCTION: SeriesType.environmental_sound_reduction,
    AppleMetricType.TIME_IN_DAYLIGHT: SeriesType.time_in_daylight,
    AppleMetricType.WATER_TEMPERATURE: SeriesType.water_temperature,
    # Environmental - Extended
    AppleMetricType.UNDERWATER_DEPTH: SeriesType.distance_other,
    # Behavioral
    AppleMetricType.NUMBER_OF_TIMES_FALLEN: SeriesType.number_of_times_fallen,
    AppleMetricType.INHALER_USAGE: SeriesType.inhaler_usage,
    AppleMetricType.NUMBER_OF_ALCOHOLIC_BEVERAGES: SeriesType.number_of_alcoholic_beverages,
    # Electrodermal
    AppleMetricType.ELECTRODERMAL_ACTIVITY: SeriesType.electrodermal_activity,
    # Ultraviolet Exposure
    AppleMetricType.UV_EXPOSURE: SeriesType.uv_exposure,
    # Wheelchair Metrics
    AppleMetricType.PUSH_COUNT: SeriesType.push_count,
    # Apple-specific Temperature
    AppleMetricType.APPLE_SLEEPING_WRIST_TEMPERATURE: SeriesType.body_temperature,
    # Atrial Fibrillation
    AppleMetricType.ATRIAL_FIBRILLATION_BURDEN: SeriesType.atrial_fibrillation_burden,
    # Workout Metrics
    AppleMetricType.WORKOUT_EFFORT_SCORE: SeriesType.workout_effort_score,
    AppleMetricType.ESTIMATED_WORKOUT_EFFORT_SCORE: SeriesType.estimated_workout_effort_score,
    # Winter/Snow Sports
    AppleMetricType.CROSS_COUNTRY_SKIING_SPEED: SeriesType.distance_other,
    # Other Sports
    AppleMetricType.PADDLE_SPORTS_SPEED: SeriesType.distance_other,
    AppleMetricType.ROWING_SPEED: SeriesType.distance_other,
    # Insulin & Other
    AppleMetricType.INSULIN_DELIVERY: SeriesType.insulin_delivery,
    # Nike Fuel
    AppleMetricType.NIKE_FUEL: SeriesType.distance_other,
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
