from enum import StrEnum

from app.schemas.series_types import SeriesType


class SDKMetricType(StrEnum):
    """Metric type identifiers for Apple HealthKit and Samsung/Health Connect SDK.

    Apple types use HKQuantityTypeIdentifier... strings.
    Samsung/HC types use uppercase SCREAMING_SNAKE_CASE strings (e.g. "HEART_RATE").
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

    # Samsung / Health Connect SDK metric types
    SDK_STEP_COUNT = "STEP_COUNT"
    SDK_HEART_RATE = "HEART_RATE"
    SDK_RESTING_HEART_RATE = "RESTING_HEART_RATE"
    SDK_HEART_RATE_VARIABILITY = "HEART_RATE_VARIABILITY"
    SDK_OXYGEN_SATURATION = "OXYGEN_SATURATION"
    SDK_BLOOD_PRESSURE_SYSTOLIC = "BLOOD_PRESSURE_SYSTOLIC"
    SDK_BLOOD_PRESSURE_DIASTOLIC = "BLOOD_PRESSURE_DIASTOLIC"
    SDK_BLOOD_GLUCOSE = "BLOOD_GLUCOSE"
    SDK_ACTIVE_CALORIES_BURNED = "ACTIVE_CALORIES_BURNED"
    SDK_BASAL_METABOLIC_RATE = "BASAL_METABOLIC_RATE"
    SDK_BODY_TEMPERATURE = "BODY_TEMPERATURE"
    SDK_WEIGHT = "WEIGHT"
    SDK_HEIGHT = "HEIGHT"
    SDK_BODY_FAT = "BODY_FAT"
    SDK_BODY_FAT_MASS = "BODY_FAT_MASS"
    SDK_LEAN_BODY_MASS = "LEAN_BODY_MASS"
    SDK_SKELETAL_MUSCLE_MASS = "SKELETAL_MUSCLE_MASS"
    SDK_BMI = "BMI"
    SDK_FLOORS_CLIMBED = "FLOORS_CLIMBED"
    SDK_DISTANCE = "DISTANCE"
    SDK_HYDRATION = "HYDRATION"
    SDK_VO2_MAX = "VO2_MAX"


METRIC_TYPE_TO_SERIES_TYPE: dict[SDKMetricType, SeriesType] = {
    # Heart & Cardiovascular
    SDKMetricType.HEART_RATE: SeriesType.heart_rate,
    SDKMetricType.RESTING_HEART_RATE: SeriesType.resting_heart_rate,
    SDKMetricType.HEART_RATE_VARIABILITY_SDNN: SeriesType.heart_rate_variability_sdnn,
    SDKMetricType.HEART_RATE_RECOVERY_ONE_MINUTE: SeriesType.heart_rate_recovery_one_minute,
    SDKMetricType.WALKING_HEART_RATE_AVERAGE: SeriesType.walking_heart_rate_average,
    # Blood & Respiratory
    SDKMetricType.OXYGEN_SATURATION: SeriesType.oxygen_saturation,
    SDKMetricType.BLOOD_GLUCOSE: SeriesType.blood_glucose,
    SDKMetricType.BLOOD_PRESSURE_SYSTOLIC: SeriesType.blood_pressure_systolic,
    SDKMetricType.BLOOD_PRESSURE_DIASTOLIC: SeriesType.blood_pressure_diastolic,
    SDKMetricType.RESPIRATORY_RATE: SeriesType.respiratory_rate,
    SDKMetricType.BASAL_BODY_TEMPERATURE: SeriesType.body_temperature,
    SDKMetricType.SLEEPING_BREATHING_DISTURBANCES: SeriesType.sleeping_breathing_disturbances,
    # Blood & Respiratory - Extended
    SDKMetricType.BLOOD_ALCOHOL_CONTENT: SeriesType.blood_alcohol_content,
    SDKMetricType.PERIPHERAL_PERFUSION_INDEX: SeriesType.peripheral_perfusion_index,
    SDKMetricType.FORCED_VITAL_CAPACITY: SeriesType.forced_vital_capacity,
    SDKMetricType.FORCED_EXPIRATORY_VOLUME_1: SeriesType.forced_expiratory_volume_1,
    SDKMetricType.PEAK_EXPIRATORY_FLOW_RATE: SeriesType.peak_expiratory_flow_rate,
    # Body Composition
    SDKMetricType.HEIGHT: SeriesType.height,
    SDKMetricType.BODY_MASS: SeriesType.weight,
    SDKMetricType.BODY_FAT_PERCENTAGE: SeriesType.body_fat_percentage,
    SDKMetricType.BODY_MASS_INDEX: SeriesType.body_mass_index,
    SDKMetricType.LEAN_BODY_MASS: SeriesType.lean_body_mass,
    SDKMetricType.BODY_TEMPERATURE: SeriesType.body_temperature,
    # Body Composition - Extended
    SDKMetricType.WAIST_CIRCUMFERENCE: SeriesType.waist_circumference,
    # Fitness Metrics
    SDKMetricType.VO2_MAX: SeriesType.vo2_max,
    SDKMetricType.SIX_MINUTE_WALK_TEST_DISTANCE: SeriesType.six_minute_walk_test_distance,
    # Activity - Basic
    SDKMetricType.STEP_COUNT: SeriesType.steps,
    SDKMetricType.ACTIVE_ENERGY_BURNED: SeriesType.energy,
    SDKMetricType.BASAL_ENERGY_BURNED: SeriesType.basal_energy,
    SDKMetricType.APPLE_STAND_TIME: SeriesType.stand_time,
    SDKMetricType.APPLE_EXERCISE_TIME: SeriesType.exercise_time,
    SDKMetricType.FLIGHTS_CLIMBED: SeriesType.flights_climbed,
    SDKMetricType.PHYSICAL_EFFORT: SeriesType.physical_effort,
    SDKMetricType.APPLE_MOVE_TIME: SeriesType.exercise_time,
    # Activity - Distance
    SDKMetricType.DISTANCE_WALKING_RUNNING: SeriesType.distance_walking_running,
    SDKMetricType.DISTANCE_CYCLING: SeriesType.distance_cycling,
    SDKMetricType.DISTANCE_SWIMMING: SeriesType.distance_swimming,
    SDKMetricType.DISTANCE_DOWNHILL_SNOW_SPORTS: SeriesType.distance_downhill_snow_sports,
    # Activity - Distance - Extended
    SDKMetricType.DISTANCE_WHEELCHAIR: SeriesType.distance_other,
    SDKMetricType.DISTANCE_CROSS_COUNTRY_SKIING: SeriesType.distance_other,
    SDKMetricType.DISTANCE_PADDLE_SPORTS: SeriesType.distance_other,
    SDKMetricType.DISTANCE_ROWING: SeriesType.distance_other,
    SDKMetricType.DISTANCE_SKATING_SPORTS: SeriesType.distance_other,
    # Walking Metrics
    SDKMetricType.WALKING_STEP_LENGTH: SeriesType.walking_step_length,
    SDKMetricType.WALKING_SPEED: SeriesType.walking_speed,
    SDKMetricType.WALKING_DOUBLE_SUPPORT_PERCENTAGE: SeriesType.walking_double_support_percentage,
    SDKMetricType.WALKING_ASYMMETRY_PERCENTAGE: SeriesType.walking_asymmetry_percentage,
    SDKMetricType.APPLE_WALKING_STEADINESS: SeriesType.walking_steadiness,
    SDKMetricType.STAIR_DESCENT_SPEED: SeriesType.stair_descent_speed,
    SDKMetricType.STAIR_ASCENT_SPEED: SeriesType.stair_ascent_speed,
    # Running Metrics
    SDKMetricType.RUNNING_POWER: SeriesType.running_power,
    SDKMetricType.RUNNING_SPEED: SeriesType.running_speed,
    SDKMetricType.RUNNING_VERTICAL_OSCILLATION: SeriesType.running_vertical_oscillation,
    SDKMetricType.RUNNING_GROUND_CONTACT_TIME: SeriesType.running_ground_contact_time,
    SDKMetricType.RUNNING_STRIDE_LENGTH: SeriesType.running_stride_length,
    # Swimming Metrics
    SDKMetricType.SWIMMING_STROKE_COUNT: SeriesType.swimming_stroke_count,
    # Cycling Metrics
    SDKMetricType.CYCLING_CADENCE: SeriesType.cadence,
    SDKMetricType.CYCLING_POWER: SeriesType.power,
    SDKMetricType.CYCLING_FUNCTIONAL_THRESHOLD_POWER: SeriesType.power,
    SDKMetricType.CYCLING_SPEED: SeriesType.speed,
    # Environmental
    SDKMetricType.ENVIRONMENTAL_AUDIO_EXPOSURE: SeriesType.environmental_audio_exposure,
    SDKMetricType.HEADPHONE_AUDIO_EXPOSURE: SeriesType.headphone_audio_exposure,
    SDKMetricType.ENVIRONMENTAL_SOUND_REDUCTION: SeriesType.environmental_sound_reduction,
    SDKMetricType.TIME_IN_DAYLIGHT: SeriesType.time_in_daylight,
    SDKMetricType.WATER_TEMPERATURE: SeriesType.water_temperature,
    # Environmental - Extended
    SDKMetricType.UNDERWATER_DEPTH: SeriesType.distance_other,
    # Behavioral
    SDKMetricType.NUMBER_OF_TIMES_FALLEN: SeriesType.number_of_times_fallen,
    SDKMetricType.INHALER_USAGE: SeriesType.inhaler_usage,
    SDKMetricType.NUMBER_OF_ALCOHOLIC_BEVERAGES: SeriesType.number_of_alcoholic_beverages,
    # Electrodermal
    SDKMetricType.ELECTRODERMAL_ACTIVITY: SeriesType.electrodermal_activity,
    # Ultraviolet Exposure
    SDKMetricType.UV_EXPOSURE: SeriesType.uv_exposure,
    # Wheelchair Metrics
    SDKMetricType.PUSH_COUNT: SeriesType.push_count,
    # Apple-specific Temperature
    SDKMetricType.APPLE_SLEEPING_WRIST_TEMPERATURE: SeriesType.body_temperature,
    # Atrial Fibrillation
    SDKMetricType.ATRIAL_FIBRILLATION_BURDEN: SeriesType.atrial_fibrillation_burden,
    # Workout Metrics
    SDKMetricType.WORKOUT_EFFORT_SCORE: SeriesType.workout_effort_score,
    SDKMetricType.ESTIMATED_WORKOUT_EFFORT_SCORE: SeriesType.estimated_workout_effort_score,
    # Winter/Snow Sports
    SDKMetricType.CROSS_COUNTRY_SKIING_SPEED: SeriesType.distance_other,
    # Other Sports
    SDKMetricType.PADDLE_SPORTS_SPEED: SeriesType.distance_other,
    SDKMetricType.ROWING_SPEED: SeriesType.distance_other,
    # Insulin & Other
    SDKMetricType.INSULIN_DELIVERY: SeriesType.insulin_delivery,
    # Nike Fuel
    SDKMetricType.NIKE_FUEL: SeriesType.distance_other,
    # Samsung / Health Connect SDK types
    SDKMetricType.SDK_STEP_COUNT: SeriesType.steps,
    SDKMetricType.SDK_HEART_RATE: SeriesType.heart_rate,
    SDKMetricType.SDK_RESTING_HEART_RATE: SeriesType.resting_heart_rate,
    SDKMetricType.SDK_HEART_RATE_VARIABILITY: SeriesType.heart_rate_variability_rmssd,
    SDKMetricType.SDK_OXYGEN_SATURATION: SeriesType.oxygen_saturation,
    SDKMetricType.SDK_BLOOD_PRESSURE_SYSTOLIC: SeriesType.blood_pressure_systolic,
    SDKMetricType.SDK_BLOOD_PRESSURE_DIASTOLIC: SeriesType.blood_pressure_diastolic,
    SDKMetricType.SDK_BLOOD_GLUCOSE: SeriesType.blood_glucose,
    SDKMetricType.SDK_ACTIVE_CALORIES_BURNED: SeriesType.energy,
    SDKMetricType.SDK_BASAL_METABOLIC_RATE: SeriesType.basal_energy,
    SDKMetricType.SDK_BODY_TEMPERATURE: SeriesType.body_temperature,
    SDKMetricType.SDK_WEIGHT: SeriesType.weight,
    SDKMetricType.SDK_HEIGHT: SeriesType.height,
    SDKMetricType.SDK_BODY_FAT: SeriesType.body_fat_percentage,
    SDKMetricType.SDK_BODY_FAT_MASS: SeriesType.body_fat_mass,
    SDKMetricType.SDK_LEAN_BODY_MASS: SeriesType.lean_body_mass,
    SDKMetricType.SDK_SKELETAL_MUSCLE_MASS: SeriesType.skeletal_muscle_mass,
    SDKMetricType.SDK_BMI: SeriesType.body_mass_index,
    SDKMetricType.SDK_FLOORS_CLIMBED: SeriesType.flights_climbed,
    SDKMetricType.SDK_DISTANCE: SeriesType.distance_walking_running,
    SDKMetricType.SDK_HYDRATION: SeriesType.hydration,
    SDKMetricType.SDK_VO2_MAX: SeriesType.vo2_max,
}


def get_series_type_from_metric_type(metric_type: SDKMetricType | str) -> SeriesType | None:
    """
    Map a metric type identifier (Apple HealthKit or Samsung/Health Connect SDK)
    to the unified SeriesType enum. Returns None when the metric type is not supported.
    """
    return METRIC_TYPE_TO_SERIES_TYPE.get(metric_type)  # type: ignore[arg-type]
