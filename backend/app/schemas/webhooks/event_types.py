"""Webhook event types emitted by Open Wearables.

Each value follows the Svix convention: ``<resource>.<action>``.
Keep in sync with the init script that registers them with the Svix server.

All events use the ``created`` action — there is no update/patch flow.

**Two-level hierarchy:**
- *Group events* (e.g. ``heart_rate.created``) fire for any sample belonging to
  that category.  Subscribe here if you want all data of a given kind.
- *Granular events* (``series.<series_type>.created``) fire for a single
  SeriesType slug.  Subscribe here if you need only a specific metric.

Both events are emitted for every ingestion batch — consumers can subscribe to
either level or both.  ``EVENT_TYPE_GROUPS`` provides the full group → granular
mapping for UI renderers and documentation generators.
"""

from enum import StrEnum


class WebhookEventType(StrEnum):
    # -------------------------------------------------------------------------
    # Provider connection events
    # -------------------------------------------------------------------------
    CONNECTION_CREATED = "connection.created"

    # -------------------------------------------------------------------------
    # EventRecord-based (discrete sessions)
    # -------------------------------------------------------------------------
    WORKOUT_CREATED = "workout.created"
    SLEEP_CREATED = "sleep.created"

    # -------------------------------------------------------------------------
    # TimeSeries — GROUP events (one per category)
    # Subscribe to a group to receive all metrics within that category.
    # -------------------------------------------------------------------------
    HEART_RATE_CREATED = "heart_rate.created"
    HEART_RATE_VARIABILITY_CREATED = "heart_rate_variability.created"
    STEPS_CREATED = "steps.created"
    CALORIES_CREATED = "calories.created"
    SPO2_CREATED = "spo2.created"
    RESPIRATORY_RATE_CREATED = "respiratory_rate.created"
    BODY_TEMPERATURE_CREATED = "body_temperature.created"
    STRESS_CREATED = "stress.created"
    BLOOD_GLUCOSE_CREATED = "blood_glucose.created"
    BLOOD_PRESSURE_CREATED = "blood_pressure.created"
    BODY_COMPOSITION_CREATED = "body_composition.created"
    FITNESS_METRICS_CREATED = "fitness_metrics.created"
    RECOVERY_SCORE_CREATED = "recovery_score.created"
    ACTIVITY_CREATED_TIMESERIES = "activity_timeseries.created"
    WORKOUT_METRICS_CREATED = "workout_metrics.created"
    ENVIRONMENTAL_CREATED = "environmental.created"

    # -------------------------------------------------------------------------
    # TimeSeries — GRANULAR events (one per SeriesType slug)
    # Prefixed with ``series.`` to distinguish from group events.
    # Subscribe here for a single specific metric.
    # -------------------------------------------------------------------------

    # Heart & Cardiovascular
    SERIES_HEART_RATE = "series.heart_rate.created"
    SERIES_RESTING_HEART_RATE = "series.resting_heart_rate.created"
    SERIES_HEART_RATE_RECOVERY_ONE_MINUTE = "series.heart_rate_recovery_one_minute.created"
    SERIES_WALKING_HEART_RATE_AVERAGE = "series.walking_heart_rate_average.created"
    SERIES_ATRIAL_FIBRILLATION_BURDEN = "series.atrial_fibrillation_burden.created"

    # HRV
    SERIES_HEART_RATE_VARIABILITY_SDNN = "series.heart_rate_variability_sdnn.created"
    SERIES_HEART_RATE_VARIABILITY_RMSSD = "series.heart_rate_variability_rmssd.created"

    # Recovery
    SERIES_GARMIN_BODY_BATTERY = "series.garmin_body_battery.created"

    # SpO2
    SERIES_OXYGEN_SATURATION = "series.oxygen_saturation.created"
    SERIES_PERIPHERAL_PERFUSION_INDEX = "series.peripheral_perfusion_index.created"

    # Blood glucose / alcohol / insulin
    SERIES_BLOOD_GLUCOSE = "series.blood_glucose.created"
    SERIES_BLOOD_ALCOHOL_CONTENT = "series.blood_alcohol_content.created"
    SERIES_INSULIN_DELIVERY = "series.insulin_delivery.created"

    # Blood pressure
    SERIES_BLOOD_PRESSURE_SYSTOLIC = "series.blood_pressure_systolic.created"
    SERIES_BLOOD_PRESSURE_DIASTOLIC = "series.blood_pressure_diastolic.created"

    # Respiratory
    SERIES_RESPIRATORY_RATE = "series.respiratory_rate.created"
    SERIES_SLEEPING_BREATHING_DISTURBANCES = "series.sleeping_breathing_disturbances.created"
    SERIES_BREATHING_DISTURBANCE_INDEX = "series.breathing_disturbance_index.created"
    SERIES_FORCED_VITAL_CAPACITY = "series.forced_vital_capacity.created"
    SERIES_FORCED_EXPIRATORY_VOLUME_1 = "series.forced_expiratory_volume_1.created"
    SERIES_PEAK_EXPIRATORY_FLOW_RATE = "series.peak_expiratory_flow_rate.created"

    # Body composition
    SERIES_HEIGHT = "series.height.created"
    SERIES_WEIGHT = "series.weight.created"
    SERIES_BODY_FAT_PERCENTAGE = "series.body_fat_percentage.created"
    SERIES_BODY_MASS_INDEX = "series.body_mass_index.created"
    SERIES_LEAN_BODY_MASS = "series.lean_body_mass.created"
    SERIES_BODY_FAT_MASS = "series.body_fat_mass.created"
    SERIES_SKELETAL_MUSCLE_MASS = "series.skeletal_muscle_mass.created"
    SERIES_WAIST_CIRCUMFERENCE = "series.waist_circumference.created"

    # Body temperature
    SERIES_BODY_TEMPERATURE = "series.body_temperature.created"
    SERIES_SKIN_TEMPERATURE = "series.skin_temperature.created"
    SERIES_SKIN_TEMPERATURE_DEVIATION = "series.skin_temperature_deviation.created"
    SERIES_SKIN_TEMPERATURE_TREND_DEVIATION = "series.skin_temperature_trend_deviation.created"
    SERIES_GARMIN_SKIN_TEMPERATURE = "series.garmin_skin_temperature.created"

    # Stress
    SERIES_GARMIN_STRESS_LEVEL = "series.garmin_stress_level.created"
    SERIES_ELECTRODERMAL_ACTIVITY = "series.electrodermal_activity.created"

    # Fitness metrics
    SERIES_VO2_MAX = "series.vo2_max.created"
    SERIES_SIX_MINUTE_WALK_TEST_DISTANCE = "series.six_minute_walk_test_distance.created"
    SERIES_CARDIOVASCULAR_AGE = "series.cardiovascular_age.created"
    SERIES_GARMIN_FITNESS_AGE = "series.garmin_fitness_age.created"

    # Steps & calories
    SERIES_STEPS = "series.steps.created"
    SERIES_ENERGY = "series.energy.created"
    SERIES_BASAL_ENERGY = "series.basal_energy.created"

    # Activity basic
    SERIES_STAND_TIME = "series.stand_time.created"
    SERIES_EXERCISE_TIME = "series.exercise_time.created"
    SERIES_PHYSICAL_EFFORT = "series.physical_effort.created"
    SERIES_FLIGHTS_CLIMBED = "series.flights_climbed.created"
    SERIES_AVERAGE_MET = "series.average_met.created"
    SERIES_PUSH_COUNT = "series.push_count.created"
    SERIES_NUMBER_OF_TIMES_FALLEN = "series.number_of_times_fallen.created"
    SERIES_NUMBER_OF_ALCOHOLIC_BEVERAGES = "series.number_of_alcoholic_beverages.created"
    SERIES_NIKE_FUEL = "series.nike_fuel.created"
    SERIES_HYDRATION = "series.hydration.created"

    # Activity distance
    SERIES_DISTANCE_WALKING_RUNNING = "series.distance_walking_running.created"
    SERIES_DISTANCE_CYCLING = "series.distance_cycling.created"
    SERIES_DISTANCE_SWIMMING = "series.distance_swimming.created"
    SERIES_DISTANCE_DOWNHILL_SNOW_SPORTS = "series.distance_downhill_snow_sports.created"
    SERIES_DISTANCE_OTHER = "series.distance_other.created"

    # Workout / sport metrics
    SERIES_CADENCE = "series.cadence.created"
    SERIES_POWER = "series.power.created"
    SERIES_SPEED = "series.speed.created"
    SERIES_WORKOUT_EFFORT_SCORE = "series.workout_effort_score.created"
    SERIES_ESTIMATED_WORKOUT_EFFORT_SCORE = "series.estimated_workout_effort_score.created"
    SERIES_WALKING_STEP_LENGTH = "series.walking_step_length.created"
    SERIES_WALKING_SPEED = "series.walking_speed.created"
    SERIES_WALKING_DOUBLE_SUPPORT_PERCENTAGE = "series.walking_double_support_percentage.created"
    SERIES_WALKING_ASYMMETRY_PERCENTAGE = "series.walking_asymmetry_percentage.created"
    SERIES_WALKING_STEADINESS = "series.walking_steadiness.created"
    SERIES_STAIR_DESCENT_SPEED = "series.stair_descent_speed.created"
    SERIES_STAIR_ASCENT_SPEED = "series.stair_ascent_speed.created"
    SERIES_RUNNING_POWER = "series.running_power.created"
    SERIES_RUNNING_SPEED = "series.running_speed.created"
    SERIES_RUNNING_VERTICAL_OSCILLATION = "series.running_vertical_oscillation.created"
    SERIES_RUNNING_GROUND_CONTACT_TIME = "series.running_ground_contact_time.created"
    SERIES_RUNNING_STRIDE_LENGTH = "series.running_stride_length.created"
    SERIES_SWIMMING_STROKE_COUNT = "series.swimming_stroke_count.created"
    SERIES_UNDERWATER_DEPTH = "series.underwater_depth.created"

    # Environmental
    SERIES_ENVIRONMENTAL_AUDIO_EXPOSURE = "series.environmental_audio_exposure.created"
    SERIES_HEADPHONE_AUDIO_EXPOSURE = "series.headphone_audio_exposure.created"
    SERIES_ENVIRONMENTAL_SOUND_REDUCTION = "series.environmental_sound_reduction.created"
    SERIES_TIME_IN_DAYLIGHT = "series.time_in_daylight.created"
    SERIES_WATER_TEMPERATURE = "series.water_temperature.created"
    SERIES_UV_EXPOSURE = "series.uv_exposure.created"
    SERIES_INHALER_USAGE = "series.inhaler_usage.created"
    SERIES_WEATHER_TEMPERATURE = "series.weather_temperature.created"
    SERIES_WEATHER_HUMIDITY = "series.weather_humidity.created"


# Human-readable descriptions shown in the Svix dashboard and event-types endpoint
EVENT_TYPE_DESCRIPTIONS: dict[WebhookEventType, str] = {
    # Session events
    WebhookEventType.CONNECTION_CREATED: "A user successfully connected a wearable provider.",
    WebhookEventType.WORKOUT_CREATED: "A new workout session was saved.",
    WebhookEventType.SLEEP_CREATED: "A new (or merged) sleep session was saved.",
    # Group events
    WebhookEventType.HEART_RATE_CREATED: "Any heart-rate samples (all HR variants) were ingested.",
    WebhookEventType.HEART_RATE_VARIABILITY_CREATED: "Any HRV samples (SDNN or RMSSD) were ingested.",
    WebhookEventType.STEPS_CREATED: "New step-count samples were ingested.",
    WebhookEventType.CALORIES_CREATED: "New calorie/energy samples were ingested.",
    WebhookEventType.SPO2_CREATED: "Any SpO2/perfusion samples were ingested.",
    WebhookEventType.RESPIRATORY_RATE_CREATED: "Any respiratory-rate or lung-function samples were ingested.",
    WebhookEventType.BODY_TEMPERATURE_CREATED: "Any body or skin temperature samples were ingested.",
    WebhookEventType.STRESS_CREATED: "Any stress or electrodermal-activity samples were ingested.",
    WebhookEventType.BLOOD_GLUCOSE_CREATED: "Any blood-glucose, alcohol or insulin samples were ingested.",
    WebhookEventType.BLOOD_PRESSURE_CREATED: "Any blood-pressure samples (systolic or diastolic) were ingested.",
    WebhookEventType.BODY_COMPOSITION_CREATED: "Any body-composition samples (weight, BMI, fat, etc.) were ingested.",
    WebhookEventType.FITNESS_METRICS_CREATED: "Any fitness-metrics samples (VO2max, cardio age, etc.) were ingested.",
    WebhookEventType.RECOVERY_SCORE_CREATED: "Any recovery-score or body-battery samples were ingested.",
    WebhookEventType.ACTIVITY_CREATED_TIMESERIES: (
        "Any activity samples (distance, stand time, flights climbed, etc.) were ingested."
    ),
    WebhookEventType.WORKOUT_METRICS_CREATED: (
        "Any workout-metrics samples (cadence, power, running/walking/swimming metrics, etc.) were ingested."
    ),
    WebhookEventType.ENVIRONMENTAL_CREATED: (
        "Any environmental samples (audio exposure, UV, weather, etc.) were ingested."
    ),
    # Granular series events
    WebhookEventType.SERIES_HEART_RATE: "Continuous heart-rate samples were ingested.",
    WebhookEventType.SERIES_RESTING_HEART_RATE: "Resting heart-rate samples were ingested.",
    WebhookEventType.SERIES_HEART_RATE_RECOVERY_ONE_MINUTE: "1-minute heart-rate recovery samples were ingested.",
    WebhookEventType.SERIES_WALKING_HEART_RATE_AVERAGE: "Walking heart-rate average samples were ingested.",
    WebhookEventType.SERIES_ATRIAL_FIBRILLATION_BURDEN: "Atrial fibrillation burden samples were ingested.",
    WebhookEventType.SERIES_HEART_RATE_VARIABILITY_SDNN: "HRV SDNN samples were ingested.",
    WebhookEventType.SERIES_HEART_RATE_VARIABILITY_RMSSD: "HRV RMSSD samples were ingested.",
    WebhookEventType.SERIES_GARMIN_BODY_BATTERY: "Garmin body battery samples were ingested.",
    WebhookEventType.SERIES_OXYGEN_SATURATION: "Blood oxygen saturation (SpO2) samples were ingested.",
    WebhookEventType.SERIES_PERIPHERAL_PERFUSION_INDEX: "Peripheral perfusion index samples were ingested.",
    WebhookEventType.SERIES_BLOOD_GLUCOSE: "Blood glucose samples were ingested.",
    WebhookEventType.SERIES_BLOOD_ALCOHOL_CONTENT: "Blood alcohol content samples were ingested.",
    WebhookEventType.SERIES_INSULIN_DELIVERY: "Insulin delivery samples were ingested.",
    WebhookEventType.SERIES_BLOOD_PRESSURE_SYSTOLIC: "Systolic blood pressure samples were ingested.",
    WebhookEventType.SERIES_BLOOD_PRESSURE_DIASTOLIC: "Diastolic blood pressure samples were ingested.",
    WebhookEventType.SERIES_RESPIRATORY_RATE: "Respiratory rate samples were ingested.",
    WebhookEventType.SERIES_SLEEPING_BREATHING_DISTURBANCES: "Sleeping breathing disturbance samples were ingested.",
    WebhookEventType.SERIES_BREATHING_DISTURBANCE_INDEX: "Breathing disturbance index samples were ingested.",
    WebhookEventType.SERIES_FORCED_VITAL_CAPACITY: "Forced vital capacity (FVC) samples were ingested.",
    WebhookEventType.SERIES_FORCED_EXPIRATORY_VOLUME_1: "Forced expiratory volume (FEV1) samples were ingested.",
    WebhookEventType.SERIES_PEAK_EXPIRATORY_FLOW_RATE: "Peak expiratory flow rate samples were ingested.",
    WebhookEventType.SERIES_HEIGHT: "Height samples were ingested.",
    WebhookEventType.SERIES_WEIGHT: "Weight samples were ingested.",
    WebhookEventType.SERIES_BODY_FAT_PERCENTAGE: "Body fat percentage samples were ingested.",
    WebhookEventType.SERIES_BODY_MASS_INDEX: "BMI samples were ingested.",
    WebhookEventType.SERIES_LEAN_BODY_MASS: "Lean body mass samples were ingested.",
    WebhookEventType.SERIES_BODY_FAT_MASS: "Body fat mass samples were ingested.",
    WebhookEventType.SERIES_SKELETAL_MUSCLE_MASS: "Skeletal muscle mass samples were ingested.",
    WebhookEventType.SERIES_WAIST_CIRCUMFERENCE: "Waist circumference samples were ingested.",
    WebhookEventType.SERIES_BODY_TEMPERATURE: "Core body temperature samples were ingested.",
    WebhookEventType.SERIES_SKIN_TEMPERATURE: "Skin temperature samples were ingested.",
    WebhookEventType.SERIES_SKIN_TEMPERATURE_DEVIATION: "Skin temperature deviation samples were ingested.",
    WebhookEventType.SERIES_SKIN_TEMPERATURE_TREND_DEVIATION: (
        "Skin temperature trend deviation samples were ingested."
    ),
    WebhookEventType.SERIES_GARMIN_SKIN_TEMPERATURE: "Garmin skin temperature samples were ingested.",
    WebhookEventType.SERIES_GARMIN_STRESS_LEVEL: "Garmin stress level samples were ingested.",
    WebhookEventType.SERIES_ELECTRODERMAL_ACTIVITY: "Electrodermal activity samples were ingested.",
    WebhookEventType.SERIES_VO2_MAX: "VO2 max samples were ingested.",
    WebhookEventType.SERIES_SIX_MINUTE_WALK_TEST_DISTANCE: "6-minute walk test distance samples were ingested.",
    WebhookEventType.SERIES_CARDIOVASCULAR_AGE: "Cardiovascular age samples were ingested.",
    WebhookEventType.SERIES_GARMIN_FITNESS_AGE: "Garmin fitness age estimates were ingested.",
    WebhookEventType.SERIES_STEPS: "Step count samples were ingested.",
    WebhookEventType.SERIES_ENERGY: "Active energy (calories) samples were ingested.",
    WebhookEventType.SERIES_BASAL_ENERGY: "Basal energy samples were ingested.",
    WebhookEventType.SERIES_STAND_TIME: "Stand time samples were ingested.",
    WebhookEventType.SERIES_EXERCISE_TIME: "Exercise time samples were ingested.",
    WebhookEventType.SERIES_PHYSICAL_EFFORT: "Physical effort samples were ingested.",
    WebhookEventType.SERIES_FLIGHTS_CLIMBED: "Flights climbed samples were ingested.",
    WebhookEventType.SERIES_AVERAGE_MET: "Average MET samples were ingested.",
    WebhookEventType.SERIES_PUSH_COUNT: "Wheelchair push count samples were ingested.",
    WebhookEventType.SERIES_NUMBER_OF_TIMES_FALLEN: "Fall count samples were ingested.",
    WebhookEventType.SERIES_NUMBER_OF_ALCOHOLIC_BEVERAGES: "Alcoholic beverage count samples were ingested.",
    WebhookEventType.SERIES_NIKE_FUEL: "Nike Fuel samples were ingested.",
    WebhookEventType.SERIES_HYDRATION: "Hydration samples were ingested.",
    WebhookEventType.SERIES_DISTANCE_WALKING_RUNNING: "Walking/running distance samples were ingested.",
    WebhookEventType.SERIES_DISTANCE_CYCLING: "Cycling distance samples were ingested.",
    WebhookEventType.SERIES_DISTANCE_SWIMMING: "Swimming distance samples were ingested.",
    WebhookEventType.SERIES_DISTANCE_DOWNHILL_SNOW_SPORTS: "Downhill snow sports distance samples were ingested.",
    WebhookEventType.SERIES_DISTANCE_OTHER: "Other activity distance samples were ingested.",
    WebhookEventType.SERIES_CADENCE: "Cadence samples were ingested.",
    WebhookEventType.SERIES_POWER: "Power output samples were ingested.",
    WebhookEventType.SERIES_SPEED: "Speed samples were ingested.",
    WebhookEventType.SERIES_WORKOUT_EFFORT_SCORE: "Workout effort score samples were ingested.",
    WebhookEventType.SERIES_ESTIMATED_WORKOUT_EFFORT_SCORE: ("Estimated workout effort score samples were ingested."),
    WebhookEventType.SERIES_WALKING_STEP_LENGTH: "Walking step length samples were ingested.",
    WebhookEventType.SERIES_WALKING_SPEED: "Walking speed samples were ingested.",
    WebhookEventType.SERIES_WALKING_DOUBLE_SUPPORT_PERCENTAGE: (
        "Walking double support percentage samples were ingested."
    ),
    WebhookEventType.SERIES_WALKING_ASYMMETRY_PERCENTAGE: "Walking asymmetry percentage samples were ingested.",
    WebhookEventType.SERIES_WALKING_STEADINESS: "Walking steadiness samples were ingested.",
    WebhookEventType.SERIES_STAIR_DESCENT_SPEED: "Stair descent speed samples were ingested.",
    WebhookEventType.SERIES_STAIR_ASCENT_SPEED: "Stair ascent speed samples were ingested.",
    WebhookEventType.SERIES_RUNNING_POWER: "Running power samples were ingested.",
    WebhookEventType.SERIES_RUNNING_SPEED: "Running speed samples were ingested.",
    WebhookEventType.SERIES_RUNNING_VERTICAL_OSCILLATION: "Running vertical oscillation samples were ingested.",
    WebhookEventType.SERIES_RUNNING_GROUND_CONTACT_TIME: "Running ground contact time samples were ingested.",
    WebhookEventType.SERIES_RUNNING_STRIDE_LENGTH: "Running stride length samples were ingested.",
    WebhookEventType.SERIES_SWIMMING_STROKE_COUNT: "Swimming stroke count samples were ingested.",
    WebhookEventType.SERIES_UNDERWATER_DEPTH: "Underwater depth samples were ingested.",
    WebhookEventType.SERIES_ENVIRONMENTAL_AUDIO_EXPOSURE: "Environmental audio exposure samples were ingested.",
    WebhookEventType.SERIES_HEADPHONE_AUDIO_EXPOSURE: "Headphone audio exposure samples were ingested.",
    WebhookEventType.SERIES_ENVIRONMENTAL_SOUND_REDUCTION: "Environmental sound reduction samples were ingested.",
    WebhookEventType.SERIES_TIME_IN_DAYLIGHT: "Time in daylight samples were ingested.",
    WebhookEventType.SERIES_WATER_TEMPERATURE: "Water temperature samples were ingested.",
    WebhookEventType.SERIES_UV_EXPOSURE: "UV exposure samples were ingested.",
    WebhookEventType.SERIES_INHALER_USAGE: "Inhaler usage samples were ingested.",
    WebhookEventType.SERIES_WEATHER_TEMPERATURE: "Weather temperature samples were ingested.",
    WebhookEventType.SERIES_WEATHER_HUMIDITY: "Weather humidity samples were ingested.",
}

# Maps each group event to its constituent granular (series.*) events.
# Used by the /event-types API to power two-level UI selectors.
EVENT_TYPE_GROUPS: dict[str, list[str]] = {
    WebhookEventType.HEART_RATE_CREATED: [
        WebhookEventType.SERIES_HEART_RATE,
        WebhookEventType.SERIES_RESTING_HEART_RATE,
        WebhookEventType.SERIES_HEART_RATE_RECOVERY_ONE_MINUTE,
        WebhookEventType.SERIES_WALKING_HEART_RATE_AVERAGE,
        WebhookEventType.SERIES_ATRIAL_FIBRILLATION_BURDEN,
    ],
    WebhookEventType.HEART_RATE_VARIABILITY_CREATED: [
        WebhookEventType.SERIES_HEART_RATE_VARIABILITY_SDNN,
        WebhookEventType.SERIES_HEART_RATE_VARIABILITY_RMSSD,
    ],
    WebhookEventType.RECOVERY_SCORE_CREATED: [
        WebhookEventType.SERIES_GARMIN_BODY_BATTERY,
    ],
    WebhookEventType.SPO2_CREATED: [
        WebhookEventType.SERIES_OXYGEN_SATURATION,
        WebhookEventType.SERIES_PERIPHERAL_PERFUSION_INDEX,
    ],
    WebhookEventType.BLOOD_GLUCOSE_CREATED: [
        WebhookEventType.SERIES_BLOOD_GLUCOSE,
        WebhookEventType.SERIES_BLOOD_ALCOHOL_CONTENT,
        WebhookEventType.SERIES_INSULIN_DELIVERY,
    ],
    WebhookEventType.BLOOD_PRESSURE_CREATED: [
        WebhookEventType.SERIES_BLOOD_PRESSURE_SYSTOLIC,
        WebhookEventType.SERIES_BLOOD_PRESSURE_DIASTOLIC,
    ],
    WebhookEventType.RESPIRATORY_RATE_CREATED: [
        WebhookEventType.SERIES_RESPIRATORY_RATE,
        WebhookEventType.SERIES_SLEEPING_BREATHING_DISTURBANCES,
        WebhookEventType.SERIES_BREATHING_DISTURBANCE_INDEX,
        WebhookEventType.SERIES_FORCED_VITAL_CAPACITY,
        WebhookEventType.SERIES_FORCED_EXPIRATORY_VOLUME_1,
        WebhookEventType.SERIES_PEAK_EXPIRATORY_FLOW_RATE,
    ],
    WebhookEventType.BODY_COMPOSITION_CREATED: [
        WebhookEventType.SERIES_HEIGHT,
        WebhookEventType.SERIES_WEIGHT,
        WebhookEventType.SERIES_BODY_FAT_PERCENTAGE,
        WebhookEventType.SERIES_BODY_MASS_INDEX,
        WebhookEventType.SERIES_LEAN_BODY_MASS,
        WebhookEventType.SERIES_BODY_FAT_MASS,
        WebhookEventType.SERIES_SKELETAL_MUSCLE_MASS,
        WebhookEventType.SERIES_WAIST_CIRCUMFERENCE,
    ],
    WebhookEventType.BODY_TEMPERATURE_CREATED: [
        WebhookEventType.SERIES_BODY_TEMPERATURE,
        WebhookEventType.SERIES_SKIN_TEMPERATURE,
        WebhookEventType.SERIES_SKIN_TEMPERATURE_DEVIATION,
        WebhookEventType.SERIES_SKIN_TEMPERATURE_TREND_DEVIATION,
        WebhookEventType.SERIES_GARMIN_SKIN_TEMPERATURE,
    ],
    WebhookEventType.STRESS_CREATED: [
        WebhookEventType.SERIES_GARMIN_STRESS_LEVEL,
        WebhookEventType.SERIES_ELECTRODERMAL_ACTIVITY,
    ],
    WebhookEventType.FITNESS_METRICS_CREATED: [
        WebhookEventType.SERIES_VO2_MAX,
        WebhookEventType.SERIES_SIX_MINUTE_WALK_TEST_DISTANCE,
        WebhookEventType.SERIES_CARDIOVASCULAR_AGE,
        WebhookEventType.SERIES_GARMIN_FITNESS_AGE,
    ],
    WebhookEventType.STEPS_CREATED: [
        WebhookEventType.SERIES_STEPS,
    ],
    WebhookEventType.CALORIES_CREATED: [
        WebhookEventType.SERIES_ENERGY,
        WebhookEventType.SERIES_BASAL_ENERGY,
    ],
    WebhookEventType.ACTIVITY_CREATED_TIMESERIES: [
        WebhookEventType.SERIES_STAND_TIME,
        WebhookEventType.SERIES_EXERCISE_TIME,
        WebhookEventType.SERIES_PHYSICAL_EFFORT,
        WebhookEventType.SERIES_FLIGHTS_CLIMBED,
        WebhookEventType.SERIES_AVERAGE_MET,
        WebhookEventType.SERIES_PUSH_COUNT,
        WebhookEventType.SERIES_NUMBER_OF_TIMES_FALLEN,
        WebhookEventType.SERIES_NUMBER_OF_ALCOHOLIC_BEVERAGES,
        WebhookEventType.SERIES_NIKE_FUEL,
        WebhookEventType.SERIES_HYDRATION,
        WebhookEventType.SERIES_DISTANCE_WALKING_RUNNING,
        WebhookEventType.SERIES_DISTANCE_CYCLING,
        WebhookEventType.SERIES_DISTANCE_SWIMMING,
        WebhookEventType.SERIES_DISTANCE_DOWNHILL_SNOW_SPORTS,
        WebhookEventType.SERIES_DISTANCE_OTHER,
    ],
    WebhookEventType.WORKOUT_METRICS_CREATED: [
        WebhookEventType.SERIES_CADENCE,
        WebhookEventType.SERIES_POWER,
        WebhookEventType.SERIES_SPEED,
        WebhookEventType.SERIES_WORKOUT_EFFORT_SCORE,
        WebhookEventType.SERIES_ESTIMATED_WORKOUT_EFFORT_SCORE,
        WebhookEventType.SERIES_WALKING_STEP_LENGTH,
        WebhookEventType.SERIES_WALKING_SPEED,
        WebhookEventType.SERIES_WALKING_DOUBLE_SUPPORT_PERCENTAGE,
        WebhookEventType.SERIES_WALKING_ASYMMETRY_PERCENTAGE,
        WebhookEventType.SERIES_WALKING_STEADINESS,
        WebhookEventType.SERIES_STAIR_DESCENT_SPEED,
        WebhookEventType.SERIES_STAIR_ASCENT_SPEED,
        WebhookEventType.SERIES_RUNNING_POWER,
        WebhookEventType.SERIES_RUNNING_SPEED,
        WebhookEventType.SERIES_RUNNING_VERTICAL_OSCILLATION,
        WebhookEventType.SERIES_RUNNING_GROUND_CONTACT_TIME,
        WebhookEventType.SERIES_RUNNING_STRIDE_LENGTH,
        WebhookEventType.SERIES_SWIMMING_STROKE_COUNT,
        WebhookEventType.SERIES_UNDERWATER_DEPTH,
    ],
    WebhookEventType.ENVIRONMENTAL_CREATED: [
        WebhookEventType.SERIES_ENVIRONMENTAL_AUDIO_EXPOSURE,
        WebhookEventType.SERIES_HEADPHONE_AUDIO_EXPOSURE,
        WebhookEventType.SERIES_ENVIRONMENTAL_SOUND_REDUCTION,
        WebhookEventType.SERIES_TIME_IN_DAYLIGHT,
        WebhookEventType.SERIES_WATER_TEMPERATURE,
        WebhookEventType.SERIES_UV_EXPOSURE,
        WebhookEventType.SERIES_INHALER_USAGE,
        WebhookEventType.SERIES_WEATHER_TEMPERATURE,
        WebhookEventType.SERIES_WEATHER_HUMIDITY,
    ],
}
