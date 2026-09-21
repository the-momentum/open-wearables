from enum import StrEnum

from app.schemas.enums import SeriesType


class SDKMetricType(StrEnum):
    """Metric type identifiers for Apple HealthKit and Samsung/Health Connect SDK.

    Apple types use HKQuantityTypeIdentifier... strings.
    Samsung/HC types use uppercase SCREAMING_SNAKE_CASE strings (e.g. "HEART_RATE").
    """

    # Heart & Cardiovascular
    APPLE_HEART_RATE = "HKQuantityTypeIdentifierHeartRate"
    ANDROID_HEART_RATE = "HEART_RATE"
    APPLE_RESTING_HEART_RATE = "HKQuantityTypeIdentifierRestingHeartRate"
    ANDROID_RESTING_HEART_RATE = "RESTING_HEART_RATE"
    APPLE_HEART_RATE_VARIABILITY_SDNN = "HKQuantityTypeIdentifierHeartRateVariabilitySDNN"
    ANDROID_HEART_RATE_VARIABILITY = "HEART_RATE_VARIABILITY"
    HEART_RATE_RECOVERY_ONE_MINUTE = "HKQuantityTypeIdentifierHeartRateRecoveryOneMinute"
    WALKING_HEART_RATE_AVERAGE = "HKQuantityTypeIdentifierWalkingHeartRateAverage"

    # Blood & Respiratory
    APPLE_OXYGEN_SATURATION = "HKQuantityTypeIdentifierOxygenSaturation"
    ANDROID_OXYGEN_SATURATION = "OXYGEN_SATURATION"
    APPLE_BLOOD_GLUCOSE = "HKQuantityTypeIdentifierBloodGlucose"
    ANDROID_BLOOD_GLUCOSE = "BLOOD_GLUCOSE"
    APPLE_BLOOD_PRESSURE_SYSTOLIC = "HKQuantityTypeIdentifierBloodPressureSystolic"
    ANDROID_BLOOD_PRESSURE_SYSTOLIC = "BLOOD_PRESSURE_SYSTOLIC"
    APPLE_BLOOD_PRESSURE_DIASTOLIC = "HKQuantityTypeIdentifierBloodPressureDiastolic"
    ANDROID_BLOOD_PRESSURE_DIASTOLIC = "BLOOD_PRESSURE_DIASTOLIC"
    APPLE_RESPIRATORY_RATE = "HKQuantityTypeIdentifierRespiratoryRate"
    ANDROID_RESPIRATORY_RATE = "RESPIRATORY_RATE"

    # Body Composition
    APPLE_HEIGHT = "HKQuantityTypeIdentifierHeight"
    ANDROID_HEIGHT = "HEIGHT"
    ANDROID_WEIGHT = "WEIGHT"
    APPLE_BODY_MASS = "HKQuantityTypeIdentifierBodyMass"
    ANDROID_LEAN_BODY_MASS = "LEAN_BODY_MASS"
    ANDROID_SKELETAL_MUSCLE_MASS = "SKELETAL_MUSCLE_MASS"
    ANDROID_BODY_FAT_MASS = "BODY_FAT_MASS"
    APPLE_BODY_FAT_PERCENTAGE = "HKQuantityTypeIdentifierBodyFatPercentage"
    ANDROID_BODY_FAT_PERCENTAGE = "BODY_FAT"
    APPLE_BODY_MASS_INDEX = "HKQuantityTypeIdentifierBodyMassIndex"
    ANDROID_BODY_MASS_INDEX = "BMI"
    LEAN_BODY_MASS = "HKQuantityTypeIdentifierLeanBodyMass"
    APPLE_BODY_TEMPERATURE = "HKQuantityTypeIdentifierBodyTemperature"
    ANDROID_BODY_TEMPERATURE = "BODY_TEMPERATURE"

    # Fitness Metrics
    APPLE_VO2_MAX = "HKQuantityTypeIdentifierVO2Max"
    ANDROID_VO2_MAX = "VO2_MAX"
    SIX_MINUTE_WALK_TEST_DISTANCE = "HKQuantityTypeIdentifierSixMinuteWalkTestDistance"

    # Activity - Basic
    APPLE_STEP_COUNT = "HKQuantityTypeIdentifierStepCount"
    ANDROID_STEP_COUNT = "STEP_COUNT"
    APPLE_ACTIVE_ENERGY_BURNED = "HKQuantityTypeIdentifierActiveEnergyBurned"
    APPLE_BASAL_ENERGY_BURNED = "HKQuantityTypeIdentifierBasalEnergyBurned"
    ANDROID_ACTIVE_CALORIES_BURNED = "ACTIVE_CALORIES_BURNED"
    ANDROID_BASAL_METABOLIC_RATE = "BASAL_METABOLIC_RATE"
    APPLE_STAND_TIME = "HKQuantityTypeIdentifierAppleStandTime"
    APPLE_EXERCISE_TIME = "HKQuantityTypeIdentifierAppleExerciseTime"
    FLIGHTS_CLIMBED = "HKQuantityTypeIdentifierFlightsClimbed"
    ANDROID_FLOORS_CLIMBED = "FLOORS_CLIMBED"

    # Activity - Distance
    ANDROID_DISTANCE = "DISTANCE"
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
    ANDROID_HYDRATION = "HYDRATION"

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

    # Health Connect top-level metric records (emitted by the Android SDK's
    # HealthConnectManager when reading PowerRecord / SpeedRecord /
    # CyclingPedalingCadenceRecord / TotalCaloriesBurnedRecord). These ride
    # in the unified import payload under the same SDKMetricType vocabulary
    # as the Apple HK identifiers and therefore need to be resolvable here.
    ANDROID_POWER = "POWER"
    ANDROID_SPEED = "SPEED"
    ANDROID_CYCLING_PEDALING_CADENCE = "CYCLING_PEDALING_CADENCE"
    ANDROID_TOTAL_CALORIES_BURNED = "TOTAL_CALORIES_BURNED"

    # Winter/Snow Sports
    CROSS_COUNTRY_SKIING_SPEED = "HKQuantityTypeIdentifierCrossCountrySkiingSpeed"

    # Water Sports
    PADDLE_SPORTS_SPEED = "HKQuantityTypeIdentifierPaddleSportsSpeed"
    ROWING_SPEED = "HKQuantityTypeIdentifierRowingSpeed"

    # Nike Fuel (deprecated but included for backwards compatibility)
    NIKE_FUEL = "HKQuantityTypeIdentifierNikeFuel"

    # Dietary / Nutrition
    APPLE_DIETARY_ENERGY_CONSUMED = "HKQuantityTypeIdentifierDietaryEnergyConsumed"
    ANDROID_DIETARY_ENERGY_CONSUMED = "ENERGY_TOTAL"
    APPLE_DIETARY_CARBOHYDRATES = "HKQuantityTypeIdentifierDietaryCarbohydrates"
    ANDROID_DIETARY_CARBOHYDRATES = "TOTAL_CARBOHYDRATE_TOTAL"
    APPLE_DIETARY_FIBER = "HKQuantityTypeIdentifierDietaryFiber"
    ANDROID_DIETARY_FIBER = "DIETARY_FIBER_TOTAL"
    APPLE_DIETARY_SUGAR = "HKQuantityTypeIdentifierDietarySugar"
    ANDROID_DIETARY_SUGAR = "SUGAR_TOTAL"
    APPLE_DIETARY_FAT_TOTAL = "HKQuantityTypeIdentifierDietaryFatTotal"
    ANDROID_DIETARY_FAT_TOTAL = "TOTAL_FAT_TOTAL"
    APPLE_DIETARY_FAT_SATURATED = "HKQuantityTypeIdentifierDietaryFatSaturated"
    ANDROID_DIETARY_FAT_SATURATED = "SATURATED_FAT_TOTAL"
    APPLE_DIETARY_FAT_MONOUNSATURATED = "HKQuantityTypeIdentifierDietaryFatMonounsaturated"
    ANDROID_DIETARY_FAT_MONOUNSATURATED = "MONOUNSATURATED_FAT_TOTAL"
    APPLE_DIETARY_FAT_POLYUNSATURATED = "HKQuantityTypeIdentifierDietaryFatPolyunsaturated"
    ANDROID_DIETARY_FAT_POLYUNSATURATED = "POLYUNSATURATED_FAT_TOTAL"
    APPLE_DIETARY_CHOLESTEROL = "HKQuantityTypeIdentifierDietaryCholesterol"
    ANDROID_DIETARY_CHOLESTEROL = "CHOLESTEROL_TOTAL"
    APPLE_DIETARY_PROTEIN = "HKQuantityTypeIdentifierDietaryProtein"
    ANDROID_DIETARY_PROTEIN = "PROTEIN_TOTAL"
    APPLE_DIETARY_SODIUM = "HKQuantityTypeIdentifierDietarySodium"
    ANDROID_DIETARY_SODIUM = "SODIUM_TOTAL"
    APPLE_DIETARY_POTASSIUM = "HKQuantityTypeIdentifierDietaryPotassium"
    ANDROID_DIETARY_POTASSIUM = "POTASSIUM_TOTAL"
    APPLE_DIETARY_CALCIUM = "HKQuantityTypeIdentifierDietaryCalcium"
    ANDROID_DIETARY_CALCIUM = "CALCIUM_TOTAL"
    APPLE_DIETARY_IRON = "HKQuantityTypeIdentifierDietaryIron"
    ANDROID_DIETARY_IRON = "IRON_TOTAL"
    APPLE_DIETARY_MAGNESIUM = "HKQuantityTypeIdentifierDietaryMagnesium"
    ANDROID_DIETARY_MAGNESIUM = "MAGNESIUM_TOTAL"
    APPLE_DIETARY_PHOSPHORUS = "HKQuantityTypeIdentifierDietaryPhosphorus"
    ANDROID_DIETARY_PHOSPHORUS = "PHOSPHORUS_TOTAL"
    APPLE_DIETARY_ZINC = "HKQuantityTypeIdentifierDietaryZinc"
    ANDROID_DIETARY_ZINC = "ZINC_TOTAL"
    APPLE_DIETARY_COPPER = "HKQuantityTypeIdentifierDietaryCopper"
    ANDROID_DIETARY_COPPER = "COPPER_TOTAL"
    APPLE_DIETARY_MANGANESE = "HKQuantityTypeIdentifierDietaryManganese"
    ANDROID_DIETARY_MANGANESE = "MANGANESE_TOTAL"
    APPLE_DIETARY_SELENIUM = "HKQuantityTypeIdentifierDietarySelenium"
    ANDROID_DIETARY_SELENIUM = "SELENIUM_TOTAL"
    APPLE_DIETARY_CHROMIUM = "HKQuantityTypeIdentifierDietaryChromium"
    ANDROID_DIETARY_CHROMIUM = "CHROMIUM_TOTAL"
    APPLE_DIETARY_MOLYBDENUM = "HKQuantityTypeIdentifierDietaryMolybdenum"
    ANDROID_DIETARY_MOLYBDENUM = "MOLYBDENUM_TOTAL"
    APPLE_DIETARY_IODINE = "HKQuantityTypeIdentifierDietaryIodine"
    ANDROID_DIETARY_IODINE = "IODINE_TOTAL"
    APPLE_DIETARY_CHLORIDE = "HKQuantityTypeIdentifierDietaryChloride"
    ANDROID_DIETARY_CHLORIDE = "CHLORIDE_TOTAL"
    APPLE_DIETARY_VITAMIN_A = "HKQuantityTypeIdentifierDietaryVitaminA"
    ANDROID_DIETARY_VITAMIN_A = "VITAMIN_A_TOTAL"
    APPLE_DIETARY_VITAMIN_B6 = "HKQuantityTypeIdentifierDietaryVitaminB6"
    ANDROID_DIETARY_VITAMIN_B6 = "VITAMIN_B6_TOTAL"
    APPLE_DIETARY_VITAMIN_B12 = "HKQuantityTypeIdentifierDietaryVitaminB12"
    ANDROID_DIETARY_VITAMIN_B12 = "VITAMIN_B12_TOTAL"
    APPLE_DIETARY_VITAMIN_C = "HKQuantityTypeIdentifierDietaryVitaminC"
    ANDROID_DIETARY_VITAMIN_C = "VITAMIN_C_TOTAL"
    APPLE_DIETARY_VITAMIN_D = "HKQuantityTypeIdentifierDietaryVitaminD"
    ANDROID_DIETARY_VITAMIN_D = "VITAMIN_D_TOTAL"
    APPLE_DIETARY_VITAMIN_E = "HKQuantityTypeIdentifierDietaryVitaminE"
    ANDROID_DIETARY_VITAMIN_E = "VITAMIN_E_TOTAL"
    APPLE_DIETARY_VITAMIN_K = "HKQuantityTypeIdentifierDietaryVitaminK"
    ANDROID_DIETARY_VITAMIN_K = "VITAMIN_K_TOTAL"
    APPLE_DIETARY_THIAMIN = "HKQuantityTypeIdentifierDietaryThiamin"
    ANDROID_DIETARY_THIAMIN = "THIAMIN_TOTAL"
    APPLE_DIETARY_RIBOFLAVIN = "HKQuantityTypeIdentifierDietaryRiboflavin"
    ANDROID_DIETARY_RIBOFLAVIN = "RIBOFLAVIN_TOTAL"
    APPLE_DIETARY_NIACIN = "HKQuantityTypeIdentifierDietaryNiacin"
    ANDROID_DIETARY_NIACIN = "NIACIN_TOTAL"
    APPLE_DIETARY_FOLATE = "HKQuantityTypeIdentifierDietaryFolate"
    ANDROID_DIETARY_FOLATE = "FOLATE_TOTAL"
    APPLE_DIETARY_PANTOTHENIC_ACID = "HKQuantityTypeIdentifierDietaryPantothenicAcid"
    ANDROID_DIETARY_PANTOTHENIC_ACID = "PANTOTHENIC_ACID_TOTAL"
    APPLE_DIETARY_BIOTIN = "HKQuantityTypeIdentifierDietaryBiotin"
    ANDROID_DIETARY_BIOTIN = "BIOTIN_TOTAL"
    APPLE_DIETARY_CAFFEINE = "HKQuantityTypeIdentifierDietaryCaffeine"
    ANDROID_DIETARY_CAFFEINE = "CAFFEINE_TOTAL"
    APPLE_DIETARY_WATER = "HKQuantityTypeIdentifierDietaryWater"


METRIC_TYPE_TO_SERIES_TYPE: dict[SDKMetricType, SeriesType] = {
    # Heart & Cardiovascular
    SDKMetricType.APPLE_HEART_RATE: SeriesType.heart_rate,
    SDKMetricType.ANDROID_HEART_RATE: SeriesType.heart_rate,
    SDKMetricType.APPLE_RESTING_HEART_RATE: SeriesType.resting_heart_rate,
    SDKMetricType.ANDROID_RESTING_HEART_RATE: SeriesType.resting_heart_rate,
    SDKMetricType.APPLE_HEART_RATE_VARIABILITY_SDNN: SeriesType.heart_rate_variability_sdnn,
    SDKMetricType.ANDROID_HEART_RATE_VARIABILITY: SeriesType.heart_rate_variability_rmssd,
    SDKMetricType.HEART_RATE_RECOVERY_ONE_MINUTE: SeriesType.heart_rate_recovery_one_minute,
    SDKMetricType.WALKING_HEART_RATE_AVERAGE: SeriesType.walking_heart_rate_average,
    # Blood & Respiratory
    SDKMetricType.APPLE_OXYGEN_SATURATION: SeriesType.oxygen_saturation,
    SDKMetricType.ANDROID_OXYGEN_SATURATION: SeriesType.oxygen_saturation,
    SDKMetricType.APPLE_BLOOD_GLUCOSE: SeriesType.blood_glucose,
    SDKMetricType.ANDROID_BLOOD_GLUCOSE: SeriesType.blood_glucose,
    SDKMetricType.APPLE_BLOOD_PRESSURE_SYSTOLIC: SeriesType.blood_pressure_systolic,
    SDKMetricType.APPLE_BLOOD_PRESSURE_DIASTOLIC: SeriesType.blood_pressure_diastolic,
    SDKMetricType.ANDROID_BLOOD_PRESSURE_SYSTOLIC: SeriesType.blood_pressure_systolic,
    SDKMetricType.ANDROID_BLOOD_PRESSURE_DIASTOLIC: SeriesType.blood_pressure_diastolic,
    SDKMetricType.APPLE_RESPIRATORY_RATE: SeriesType.respiratory_rate,
    SDKMetricType.ANDROID_RESPIRATORY_RATE: SeriesType.respiratory_rate,
    SDKMetricType.BASAL_BODY_TEMPERATURE: SeriesType.body_temperature,
    SDKMetricType.SLEEPING_BREATHING_DISTURBANCES: SeriesType.sleeping_breathing_disturbances,
    # Blood & Respiratory - Extended
    SDKMetricType.BLOOD_ALCOHOL_CONTENT: SeriesType.blood_alcohol_content,
    SDKMetricType.PERIPHERAL_PERFUSION_INDEX: SeriesType.peripheral_perfusion_index,
    SDKMetricType.FORCED_VITAL_CAPACITY: SeriesType.forced_vital_capacity,
    SDKMetricType.FORCED_EXPIRATORY_VOLUME_1: SeriesType.forced_expiratory_volume_1,
    SDKMetricType.PEAK_EXPIRATORY_FLOW_RATE: SeriesType.peak_expiratory_flow_rate,
    # Body Composition
    SDKMetricType.APPLE_HEIGHT: SeriesType.height,
    SDKMetricType.ANDROID_HEIGHT: SeriesType.height,
    SDKMetricType.APPLE_BODY_MASS: SeriesType.weight,
    SDKMetricType.ANDROID_WEIGHT: SeriesType.weight,
    SDKMetricType.APPLE_BODY_FAT_PERCENTAGE: SeriesType.body_fat_percentage,
    SDKMetricType.ANDROID_BODY_FAT_PERCENTAGE: SeriesType.body_fat_percentage,
    SDKMetricType.ANDROID_BODY_FAT_MASS: SeriesType.body_fat_mass,
    SDKMetricType.APPLE_BODY_MASS_INDEX: SeriesType.body_mass_index,
    SDKMetricType.ANDROID_BODY_MASS_INDEX: SeriesType.body_mass_index,
    SDKMetricType.LEAN_BODY_MASS: SeriesType.lean_body_mass,
    SDKMetricType.ANDROID_LEAN_BODY_MASS: SeriesType.lean_body_mass,
    SDKMetricType.ANDROID_SKELETAL_MUSCLE_MASS: SeriesType.skeletal_muscle_mass,
    SDKMetricType.APPLE_BODY_TEMPERATURE: SeriesType.body_temperature,
    SDKMetricType.ANDROID_BODY_TEMPERATURE: SeriesType.body_temperature,
    # Body Composition - Extended
    SDKMetricType.WAIST_CIRCUMFERENCE: SeriesType.waist_circumference,
    # Fitness Metrics
    SDKMetricType.APPLE_VO2_MAX: SeriesType.vo2_max,
    SDKMetricType.ANDROID_VO2_MAX: SeriesType.vo2_max,
    SDKMetricType.SIX_MINUTE_WALK_TEST_DISTANCE: SeriesType.six_minute_walk_test_distance,
    # Activity - Basic
    SDKMetricType.APPLE_STEP_COUNT: SeriesType.steps,
    SDKMetricType.ANDROID_STEP_COUNT: SeriesType.steps,
    SDKMetricType.APPLE_ACTIVE_ENERGY_BURNED: SeriesType.active_energy,
    SDKMetricType.APPLE_BASAL_ENERGY_BURNED: SeriesType.basal_energy,
    SDKMetricType.ANDROID_ACTIVE_CALORIES_BURNED: SeriesType.active_energy,
    SDKMetricType.ANDROID_BASAL_METABOLIC_RATE: SeriesType.basal_energy,
    SDKMetricType.APPLE_STAND_TIME: SeriesType.stand_time,
    SDKMetricType.APPLE_EXERCISE_TIME: SeriesType.exercise_time,
    SDKMetricType.FLIGHTS_CLIMBED: SeriesType.flights_climbed,
    SDKMetricType.ANDROID_FLOORS_CLIMBED: SeriesType.flights_climbed,
    SDKMetricType.PHYSICAL_EFFORT: SeriesType.physical_effort,
    SDKMetricType.APPLE_MOVE_TIME: SeriesType.exercise_time,
    # Activity - Distance
    SDKMetricType.ANDROID_DISTANCE: SeriesType.distance_walking_running,
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
    # Health Connect top-level metric records
    SDKMetricType.ANDROID_POWER: SeriesType.power,
    SDKMetricType.ANDROID_SPEED: SeriesType.speed,
    SDKMetricType.ANDROID_CYCLING_PEDALING_CADENCE: SeriesType.cadence,
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
    SDKMetricType.ANDROID_HYDRATION: SeriesType.hydration,
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
    # Dietary / Nutrition
    SDKMetricType.APPLE_DIETARY_ENERGY_CONSUMED: SeriesType.dietary_energy_consumed,
    SDKMetricType.ANDROID_DIETARY_ENERGY_CONSUMED: SeriesType.dietary_energy_consumed,
    SDKMetricType.APPLE_DIETARY_CARBOHYDRATES: SeriesType.dietary_carbohydrates,
    SDKMetricType.ANDROID_DIETARY_CARBOHYDRATES: SeriesType.dietary_carbohydrates,
    SDKMetricType.APPLE_DIETARY_FIBER: SeriesType.dietary_fiber,
    SDKMetricType.ANDROID_DIETARY_FIBER: SeriesType.dietary_fiber,
    SDKMetricType.APPLE_DIETARY_SUGAR: SeriesType.dietary_sugar,
    SDKMetricType.ANDROID_DIETARY_SUGAR: SeriesType.dietary_sugar,
    SDKMetricType.APPLE_DIETARY_FAT_TOTAL: SeriesType.dietary_fat_total,
    SDKMetricType.ANDROID_DIETARY_FAT_TOTAL: SeriesType.dietary_fat_total,
    SDKMetricType.APPLE_DIETARY_FAT_SATURATED: SeriesType.dietary_fat_saturated,
    SDKMetricType.ANDROID_DIETARY_FAT_SATURATED: SeriesType.dietary_fat_saturated,
    SDKMetricType.APPLE_DIETARY_FAT_MONOUNSATURATED: SeriesType.dietary_fat_monounsaturated,
    SDKMetricType.ANDROID_DIETARY_FAT_MONOUNSATURATED: SeriesType.dietary_fat_monounsaturated,
    SDKMetricType.APPLE_DIETARY_FAT_POLYUNSATURATED: SeriesType.dietary_fat_polyunsaturated,
    SDKMetricType.ANDROID_DIETARY_FAT_POLYUNSATURATED: SeriesType.dietary_fat_polyunsaturated,
    SDKMetricType.APPLE_DIETARY_CHOLESTEROL: SeriesType.dietary_cholesterol,
    SDKMetricType.ANDROID_DIETARY_CHOLESTEROL: SeriesType.dietary_cholesterol,
    SDKMetricType.APPLE_DIETARY_PROTEIN: SeriesType.dietary_protein,
    SDKMetricType.ANDROID_DIETARY_PROTEIN: SeriesType.dietary_protein,
    SDKMetricType.APPLE_DIETARY_SODIUM: SeriesType.dietary_sodium,
    SDKMetricType.ANDROID_DIETARY_SODIUM: SeriesType.dietary_sodium,
    SDKMetricType.APPLE_DIETARY_POTASSIUM: SeriesType.dietary_potassium,
    SDKMetricType.ANDROID_DIETARY_POTASSIUM: SeriesType.dietary_potassium,
    SDKMetricType.APPLE_DIETARY_CALCIUM: SeriesType.dietary_calcium,
    SDKMetricType.ANDROID_DIETARY_CALCIUM: SeriesType.dietary_calcium,
    SDKMetricType.APPLE_DIETARY_IRON: SeriesType.dietary_iron,
    SDKMetricType.ANDROID_DIETARY_IRON: SeriesType.dietary_iron,
    SDKMetricType.APPLE_DIETARY_MAGNESIUM: SeriesType.dietary_magnesium,
    SDKMetricType.ANDROID_DIETARY_MAGNESIUM: SeriesType.dietary_magnesium,
    SDKMetricType.APPLE_DIETARY_PHOSPHORUS: SeriesType.dietary_phosphorus,
    SDKMetricType.ANDROID_DIETARY_PHOSPHORUS: SeriesType.dietary_phosphorus,
    SDKMetricType.APPLE_DIETARY_ZINC: SeriesType.dietary_zinc,
    SDKMetricType.ANDROID_DIETARY_ZINC: SeriesType.dietary_zinc,
    SDKMetricType.APPLE_DIETARY_COPPER: SeriesType.dietary_copper,
    SDKMetricType.ANDROID_DIETARY_COPPER: SeriesType.dietary_copper,
    SDKMetricType.APPLE_DIETARY_MANGANESE: SeriesType.dietary_manganese,
    SDKMetricType.ANDROID_DIETARY_MANGANESE: SeriesType.dietary_manganese,
    SDKMetricType.APPLE_DIETARY_SELENIUM: SeriesType.dietary_selenium,
    SDKMetricType.ANDROID_DIETARY_SELENIUM: SeriesType.dietary_selenium,
    SDKMetricType.APPLE_DIETARY_CHROMIUM: SeriesType.dietary_chromium,
    SDKMetricType.ANDROID_DIETARY_CHROMIUM: SeriesType.dietary_chromium,
    SDKMetricType.APPLE_DIETARY_MOLYBDENUM: SeriesType.dietary_molybdenum,
    SDKMetricType.ANDROID_DIETARY_MOLYBDENUM: SeriesType.dietary_molybdenum,
    SDKMetricType.APPLE_DIETARY_IODINE: SeriesType.dietary_iodine,
    SDKMetricType.ANDROID_DIETARY_IODINE: SeriesType.dietary_iodine,
    SDKMetricType.APPLE_DIETARY_CHLORIDE: SeriesType.dietary_chloride,
    SDKMetricType.ANDROID_DIETARY_CHLORIDE: SeriesType.dietary_chloride,
    SDKMetricType.APPLE_DIETARY_VITAMIN_A: SeriesType.dietary_vitamin_a,
    SDKMetricType.ANDROID_DIETARY_VITAMIN_A: SeriesType.dietary_vitamin_a,
    SDKMetricType.APPLE_DIETARY_VITAMIN_B6: SeriesType.dietary_vitamin_b6,
    SDKMetricType.ANDROID_DIETARY_VITAMIN_B6: SeriesType.dietary_vitamin_b6,
    SDKMetricType.APPLE_DIETARY_VITAMIN_B12: SeriesType.dietary_vitamin_b12,
    SDKMetricType.ANDROID_DIETARY_VITAMIN_B12: SeriesType.dietary_vitamin_b12,
    SDKMetricType.APPLE_DIETARY_VITAMIN_C: SeriesType.dietary_vitamin_c,
    SDKMetricType.ANDROID_DIETARY_VITAMIN_C: SeriesType.dietary_vitamin_c,
    SDKMetricType.APPLE_DIETARY_VITAMIN_D: SeriesType.dietary_vitamin_d,
    SDKMetricType.ANDROID_DIETARY_VITAMIN_D: SeriesType.dietary_vitamin_d,
    SDKMetricType.APPLE_DIETARY_VITAMIN_E: SeriesType.dietary_vitamin_e,
    SDKMetricType.ANDROID_DIETARY_VITAMIN_E: SeriesType.dietary_vitamin_e,
    SDKMetricType.APPLE_DIETARY_VITAMIN_K: SeriesType.dietary_vitamin_k,
    SDKMetricType.ANDROID_DIETARY_VITAMIN_K: SeriesType.dietary_vitamin_k,
    SDKMetricType.APPLE_DIETARY_THIAMIN: SeriesType.dietary_thiamin,
    SDKMetricType.ANDROID_DIETARY_THIAMIN: SeriesType.dietary_thiamin,
    SDKMetricType.APPLE_DIETARY_RIBOFLAVIN: SeriesType.dietary_riboflavin,
    SDKMetricType.ANDROID_DIETARY_RIBOFLAVIN: SeriesType.dietary_riboflavin,
    SDKMetricType.APPLE_DIETARY_NIACIN: SeriesType.dietary_niacin,
    SDKMetricType.ANDROID_DIETARY_NIACIN: SeriesType.dietary_niacin,
    SDKMetricType.APPLE_DIETARY_FOLATE: SeriesType.dietary_folate,
    SDKMetricType.ANDROID_DIETARY_FOLATE: SeriesType.dietary_folate,
    SDKMetricType.APPLE_DIETARY_PANTOTHENIC_ACID: SeriesType.dietary_pantothenic_acid,
    SDKMetricType.ANDROID_DIETARY_PANTOTHENIC_ACID: SeriesType.dietary_pantothenic_acid,
    SDKMetricType.APPLE_DIETARY_BIOTIN: SeriesType.dietary_biotin,
    SDKMetricType.ANDROID_DIETARY_BIOTIN: SeriesType.dietary_biotin,
    SDKMetricType.APPLE_DIETARY_CAFFEINE: SeriesType.dietary_caffeine,
    SDKMetricType.ANDROID_DIETARY_CAFFEINE: SeriesType.dietary_caffeine,
    SDKMetricType.APPLE_DIETARY_WATER: SeriesType.hydration,
}


APPLE_METRIC_TYPE_TO_SERIES_TYPE: dict[SDKMetricType, SeriesType] = {
    k: v for k, v in METRIC_TYPE_TO_SERIES_TYPE.items() if k.value.startswith("HK")
}

ANDROID_METRIC_TYPE_TO_SERIES_TYPE: dict[SDKMetricType, SeriesType] = {
    k: v for k, v in METRIC_TYPE_TO_SERIES_TYPE.items() if not k.value.startswith("HK")
}


def get_series_type_from_metric_type(metric_type: SDKMetricType | str) -> SeriesType | None:
    """
    Map a metric type identifier (Apple HealthKit or Samsung/Health Connect SDK)
    to the unified SeriesType enum. Returns None when the metric type is not supported.
    """
    return METRIC_TYPE_TO_SERIES_TYPE.get(metric_type)
