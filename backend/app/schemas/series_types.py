"""Unified series type definitions for time-series data.

This module contains:
- SeriesType enum with all supported metric types (internal use)
- Stable integer IDs for database persistence
- Unit definitions for each series type
- Helper functions for ID/enum conversions and category validation

IMPORTANT: Never change existing IDs - only add new ones. IDs are persisted in the database.
"""

from enum import Enum


class SeriesType(str, Enum):
    """All supported time-series metric types."""

    # =========================================================================
    # BIOMETRICS - Heart & Cardiovascular (IDs 1-19)
    # =========================================================================
    heart_rate = "heart_rate"
    resting_heart_rate = "resting_heart_rate"
    heart_rate_variability_sdnn = "heart_rate_variability_sdnn"
    heart_rate_recovery_one_minute = "heart_rate_recovery_one_minute"
    walking_heart_rate_average = "walking_heart_rate_average"
    recovery_score = "recovery_score"
    heart_rate_variability_rmssd = "heart_rate_variability_rmssd"

    # =========================================================================
    # BIOMETRICS - Blood & Respiratory (IDs 20-39)
    # =========================================================================
    oxygen_saturation = "oxygen_saturation"
    blood_glucose = "blood_glucose"
    blood_pressure_systolic = "blood_pressure_systolic"
    blood_pressure_diastolic = "blood_pressure_diastolic"
    respiratory_rate = "respiratory_rate"
    sleeping_breathing_disturbances = "sleeping_breathing_disturbances"

    # Blood & Respiratory - Extended
    blood_alcohol_content = "blood_alcohol_content"
    peripheral_perfusion_index = "peripheral_perfusion_index"
    forced_vital_capacity = "forced_vital_capacity"
    forced_expiratory_volume_1 = "forced_expiratory_volume_1"
    peak_expiratory_flow_rate = "peak_expiratory_flow_rate"

    # =========================================================================
    # BIOMETRICS - Body Composition (IDs 40-59)
    # =========================================================================
    height = "height"
    weight = "weight"
    body_fat_percentage = "body_fat_percentage"
    body_mass_index = "body_mass_index"
    lean_body_mass = "lean_body_mass"
    body_temperature = "body_temperature"
    skin_temperature = "skin_temperature"

    # Body Composition - Extended
    waist_circumference = "waist_circumference"
    body_fat_mass = "body_fat_mass"
    skeletal_muscle_mass = "skeletal_muscle_mass"

    # =========================================================================
    # BIOMETRICS - Fitness Metrics (IDs 60-79)
    # =========================================================================
    vo2_max = "vo2_max"
    six_minute_walk_test_distance = "six_minute_walk_test_distance"

    # =========================================================================
    # ACTIVITY - Basic (IDs 80-99)
    # =========================================================================
    steps = "steps"
    energy = "energy"  # Active energy burned
    basal_energy = "basal_energy"
    stand_time = "stand_time"
    exercise_time = "exercise_time"
    physical_effort = "physical_effort"
    flights_climbed = "flights_climbed"
    average_met = "average_met"

    # =========================================================================
    # ACTIVITY - Distance (IDs 100-119)
    # =========================================================================
    distance_walking_running = "distance_walking_running"
    distance_cycling = "distance_cycling"
    distance_swimming = "distance_swimming"
    distance_downhill_snow_sports = "distance_downhill_snow_sports"
    distance_other = "distance_other"

    # =========================================================================
    # ACTIVITY - Walking Metrics (IDs 120-139)
    # =========================================================================
    walking_step_length = "walking_step_length"
    walking_speed = "walking_speed"
    walking_double_support_percentage = "walking_double_support_percentage"
    walking_asymmetry_percentage = "walking_asymmetry_percentage"
    walking_steadiness = "walking_steadiness"
    stair_descent_speed = "stair_descent_speed"
    stair_ascent_speed = "stair_ascent_speed"

    # =========================================================================
    # ACTIVITY - Running Metrics (IDs 140-159)
    # =========================================================================
    running_power = "running_power"
    running_speed = "running_speed"
    running_vertical_oscillation = "running_vertical_oscillation"
    running_ground_contact_time = "running_ground_contact_time"
    running_stride_length = "running_stride_length"

    # =========================================================================
    # ACTIVITY - Swimming Metrics (IDs 160-179)
    # =========================================================================
    swimming_stroke_count = "swimming_stroke_count"
    underwater_depth = "underwater_depth"

    # =========================================================================
    # ACTIVITY - Generic (IDs 180-199)
    # =========================================================================
    cadence = "cadence"
    power = "power"
    speed = "speed"

    # Generic Activity Metrics
    workout_effort_score = "workout_effort_score"
    estimated_workout_effort_score = "estimated_workout_effort_score"

    # =========================================================================
    # ENVIRONMENTAL (IDs 200-219)
    # =========================================================================
    environmental_audio_exposure = "environmental_audio_exposure"
    headphone_audio_exposure = "headphone_audio_exposure"
    environmental_sound_reduction = "environmental_sound_reduction"
    time_in_daylight = "time_in_daylight"
    water_temperature = "water_temperature"
    uv_exposure = "uv_exposure"
    inhaler_usage = "inhaler_usage"
    weather_temperature = "weather_temperature"
    weather_humidity = "weather_humidity"

    # =========================================================================
    # GARMIN-SPECIFIC METRICS (IDs 220-239)
    # =========================================================================
    garmin_stress_level = "garmin_stress_level"  # Garmin stress score (1-100)
    garmin_skin_temperature = "garmin_skin_temperature"  # Skin temp deviation from baseline
    garmin_fitness_age = "garmin_fitness_age"  # Garmin fitness age estimate
    garmin_body_battery = "garmin_body_battery"  # Garmin body battery (0-100)

    # =========================================================================
    # OTHER (IDs 500-)
    # =========================================================================

    electrodermal_activity = "electrodermal_activity"
    push_count = "push_count"
    atrial_fibrillation_burden = "atrial_fibrillation_burden"
    insulin_delivery = "insulin_delivery"
    number_of_times_fallen = "number_of_times_fallen"
    number_of_alcoholic_beverages = "number_of_alcoholic_beverages"
    nike_fuel = "nike_fuel"
    hydration = "hydration"


# =============================================================================
# DATABASE ID DEFINITIONS
# =============================================================================
# Stable integer identifiers for each series type. These IDs are persisted in the database.
# IMPORTANT: Never change existing IDs - only add new ones at the end of each category.

SERIES_TYPE_DEFINITIONS: list[tuple[int, SeriesType, str]] = [
    # -------------------------------------------------------------------------
    # BIOMETRICS - Heart & Cardiovascular (IDs 1-19)
    # -------------------------------------------------------------------------
    (1, SeriesType.heart_rate, "bpm"),
    (2, SeriesType.resting_heart_rate, "bpm"),
    (3, SeriesType.heart_rate_variability_sdnn, "ms"),
    (4, SeriesType.heart_rate_recovery_one_minute, "bpm"),
    (5, SeriesType.walking_heart_rate_average, "bpm"),
    (6, SeriesType.recovery_score, "score"),
    (7, SeriesType.heart_rate_variability_rmssd, "ms"),
    # -------------------------------------------------------------------------
    # BIOMETRICS - Blood & Respiratory (IDs 20-39)
    # -------------------------------------------------------------------------
    (20, SeriesType.oxygen_saturation, "percent"),
    (21, SeriesType.blood_glucose, "mg_dl"),
    (22, SeriesType.blood_pressure_systolic, "mmHg"),
    (23, SeriesType.blood_pressure_diastolic, "mmHg"),
    (24, SeriesType.respiratory_rate, "brpm"),
    (25, SeriesType.sleeping_breathing_disturbances, "count"),
    (26, SeriesType.blood_alcohol_content, "mg_dl"),
    (27, SeriesType.peripheral_perfusion_index, "score"),
    (28, SeriesType.forced_vital_capacity, "liters"),
    (29, SeriesType.forced_expiratory_volume_1, "liters"),
    (30, SeriesType.peak_expiratory_flow_rate, "liters"),
    # -------------------------------------------------------------------------
    # BIOMETRICS - Body Composition (IDs 40-59)
    # -------------------------------------------------------------------------
    (40, SeriesType.height, "cm"),
    (41, SeriesType.weight, "kg"),
    (42, SeriesType.body_fat_percentage, "percent"),
    (43, SeriesType.body_mass_index, "kg_m2"),
    (44, SeriesType.lean_body_mass, "kg"),
    (45, SeriesType.body_temperature, "celsius"),
    (46, SeriesType.skin_temperature, "celsius"),
    (47, SeriesType.waist_circumference, "cm"),
    (48, SeriesType.body_fat_mass, "kg"),
    (49, SeriesType.skeletal_muscle_mass, "kg"),
    # -------------------------------------------------------------------------
    # BIOMETRICS - Fitness Metrics (IDs 60-79)
    # -------------------------------------------------------------------------
    (60, SeriesType.vo2_max, "ml_kg_min"),
    (61, SeriesType.six_minute_walk_test_distance, "meters"),
    # -------------------------------------------------------------------------
    # ACTIVITY - Basic (IDs 80-99)
    # -------------------------------------------------------------------------
    (80, SeriesType.steps, "count"),
    (81, SeriesType.energy, "kcal"),
    (82, SeriesType.basal_energy, "kcal"),
    (83, SeriesType.stand_time, "minutes"),
    (84, SeriesType.exercise_time, "minutes"),
    (85, SeriesType.physical_effort, "score"),
    (86, SeriesType.flights_climbed, "count"),
    (87, SeriesType.average_met, "met"),
    # -------------------------------------------------------------------------
    # ACTIVITY - Distance (IDs 100-119)
    # -------------------------------------------------------------------------
    (100, SeriesType.distance_walking_running, "meters"),
    (101, SeriesType.distance_cycling, "meters"),
    (102, SeriesType.distance_swimming, "meters"),
    (103, SeriesType.distance_downhill_snow_sports, "meters"),
    (104, SeriesType.distance_other, "meters"),
    # -------------------------------------------------------------------------
    # ACTIVITY - Walking Metrics (IDs 120-139)
    # -------------------------------------------------------------------------
    (120, SeriesType.walking_step_length, "cm"),
    (121, SeriesType.walking_speed, "m_per_s"),
    (122, SeriesType.walking_double_support_percentage, "percent"),
    (123, SeriesType.walking_asymmetry_percentage, "percent"),
    (124, SeriesType.walking_steadiness, "percent"),
    (125, SeriesType.stair_descent_speed, "m_per_s"),
    (126, SeriesType.stair_ascent_speed, "m_per_s"),
    # -------------------------------------------------------------------------
    # ACTIVITY - Running Metrics (IDs 140-159)
    # -------------------------------------------------------------------------
    (140, SeriesType.running_power, "watts"),
    (141, SeriesType.running_speed, "m_per_s"),
    (142, SeriesType.running_vertical_oscillation, "cm"),
    (143, SeriesType.running_ground_contact_time, "ms"),
    (144, SeriesType.running_stride_length, "cm"),
    # -------------------------------------------------------------------------
    # ACTIVITY - Swimming Metrics (IDs 160-179)
    # -------------------------------------------------------------------------
    (160, SeriesType.swimming_stroke_count, "count"),
    (161, SeriesType.underwater_depth, "meters"),
    # -------------------------------------------------------------------------
    # ACTIVITY - Generic (IDs 180-199)
    # -------------------------------------------------------------------------
    (180, SeriesType.cadence, "rpm"),
    (181, SeriesType.power, "watts"),
    (182, SeriesType.speed, "m_per_s"),
    (183, SeriesType.workout_effort_score, "score"),
    (184, SeriesType.estimated_workout_effort_score, "score"),
    # -------------------------------------------------------------------------
    # ENVIRONMENTAL (IDs 200-219)
    # -------------------------------------------------------------------------
    (200, SeriesType.environmental_audio_exposure, "dB"),
    (201, SeriesType.headphone_audio_exposure, "dB"),
    (202, SeriesType.environmental_sound_reduction, "dB"),
    (203, SeriesType.time_in_daylight, "minutes"),
    (204, SeriesType.water_temperature, "celsius"),
    (205, SeriesType.uv_exposure, "count"),
    (206, SeriesType.inhaler_usage, "count"),
    (207, SeriesType.weather_temperature, "celsius"),
    (208, SeriesType.weather_humidity, "percent"),
    # -------------------------------------------------------------------------
    # GARMIN-SPECIFIC METRICS (IDs 220-239)
    # -------------------------------------------------------------------------
    (220, SeriesType.garmin_stress_level, "score"),
    (221, SeriesType.garmin_skin_temperature, "celsius"),  # kept for backwards compatibility
    (222, SeriesType.garmin_fitness_age, "years"),
    (223, SeriesType.garmin_body_battery, "percent"),
    # -------------------------------------------------------------------------
    # OTHER (IDs 500-)
    # -------------------------------------------------------------------------
    (500, SeriesType.electrodermal_activity, "count"),
    (501, SeriesType.push_count, "count"),
    (502, SeriesType.atrial_fibrillation_burden, "count"),
    (503, SeriesType.insulin_delivery, "count"),
    (504, SeriesType.number_of_times_fallen, "count"),
    (505, SeriesType.number_of_alcoholic_beverages, "count"),
    (506, SeriesType.nike_fuel, "count"),
    (507, SeriesType.hydration, "mL"),
]


# =============================================================================
# LOOKUP DICTIONARIES
# =============================================================================

SERIES_TYPE_ID_BY_ENUM: dict[SeriesType, int] = {enum: type_id for type_id, enum, _ in SERIES_TYPE_DEFINITIONS}
SERIES_TYPE_ENUM_BY_ID: dict[int, SeriesType] = {type_id: enum for type_id, enum, _ in SERIES_TYPE_DEFINITIONS}
SERIES_TYPE_UNIT_BY_ENUM: dict[SeriesType, str] = {enum: unit for _, enum, unit in SERIES_TYPE_DEFINITIONS}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def get_series_type_id(series_type: SeriesType) -> int:
    """Get the database ID for a series type enum."""
    return SERIES_TYPE_ID_BY_ENUM[series_type]


def get_series_type_from_id(series_type_id: int) -> SeriesType:
    """Get the series type enum from a database ID."""
    return SERIES_TYPE_ENUM_BY_ID[series_type_id]


def get_series_type_unit(series_type: SeriesType) -> str:
    """Get the unit string for a series type."""
    return SERIES_TYPE_UNIT_BY_ENUM[series_type]


# =============================================================================
# AGGREGATION METHOD DEFINITIONS
# =============================================================================


class AggregationMethod(str, Enum):
    """How a series type should be aggregated when archiving into daily rows.

    - SUM: cumulative metrics (steps, distance, calories, counts, durations)
    - AVG: rate / level metrics (heart rate, temperature, SpO2, scores)
    - MAX: peak metrics (best test distance)
    """

    SUM = "sum"
    AVG = "avg"
    MAX = "max"


# Maps each SeriesType to its primary aggregation method when reading from archive.
# The archive table always stores avg/min/max/sum — this defines which column is
# the "canonical" daily value for each type.
AGGREGATION_METHOD_BY_TYPE: dict[SeriesType, AggregationMethod] = {
    # ── Heart & Cardiovascular ──
    SeriesType.heart_rate: AggregationMethod.AVG,
    SeriesType.resting_heart_rate: AggregationMethod.AVG,
    SeriesType.heart_rate_variability_sdnn: AggregationMethod.AVG,
    SeriesType.heart_rate_recovery_one_minute: AggregationMethod.AVG,
    SeriesType.walking_heart_rate_average: AggregationMethod.AVG,
    SeriesType.recovery_score: AggregationMethod.AVG,
    SeriesType.heart_rate_variability_rmssd: AggregationMethod.AVG,
    # ── Blood & Respiratory ──
    SeriesType.oxygen_saturation: AggregationMethod.AVG,
    SeriesType.blood_glucose: AggregationMethod.AVG,
    SeriesType.blood_pressure_systolic: AggregationMethod.AVG,
    SeriesType.blood_pressure_diastolic: AggregationMethod.AVG,
    SeriesType.respiratory_rate: AggregationMethod.AVG,
    SeriesType.sleeping_breathing_disturbances: AggregationMethod.SUM,
    SeriesType.blood_alcohol_content: AggregationMethod.AVG,
    SeriesType.peripheral_perfusion_index: AggregationMethod.AVG,
    SeriesType.forced_vital_capacity: AggregationMethod.AVG,
    SeriesType.forced_expiratory_volume_1: AggregationMethod.AVG,
    SeriesType.peak_expiratory_flow_rate: AggregationMethod.AVG,
    # ── Body Composition ──
    SeriesType.height: AggregationMethod.AVG,
    SeriesType.weight: AggregationMethod.AVG,
    SeriesType.body_fat_percentage: AggregationMethod.AVG,
    SeriesType.body_mass_index: AggregationMethod.AVG,
    SeriesType.lean_body_mass: AggregationMethod.AVG,
    SeriesType.body_temperature: AggregationMethod.AVG,
    SeriesType.skin_temperature: AggregationMethod.AVG,
    SeriesType.waist_circumference: AggregationMethod.AVG,
    # ── Fitness Metrics ──
    SeriesType.vo2_max: AggregationMethod.AVG,
    SeriesType.six_minute_walk_test_distance: AggregationMethod.MAX,
    # ── Activity — Basic ──
    SeriesType.steps: AggregationMethod.SUM,
    SeriesType.energy: AggregationMethod.SUM,
    SeriesType.basal_energy: AggregationMethod.SUM,
    SeriesType.stand_time: AggregationMethod.SUM,
    SeriesType.exercise_time: AggregationMethod.SUM,
    SeriesType.physical_effort: AggregationMethod.AVG,
    SeriesType.flights_climbed: AggregationMethod.SUM,
    SeriesType.average_met: AggregationMethod.AVG,
    # ── Activity — Distance ──
    SeriesType.distance_walking_running: AggregationMethod.SUM,
    SeriesType.distance_cycling: AggregationMethod.SUM,
    SeriesType.distance_swimming: AggregationMethod.SUM,
    SeriesType.distance_downhill_snow_sports: AggregationMethod.SUM,
    SeriesType.distance_other: AggregationMethod.SUM,
    # ── Activity — Walking Metrics ──
    SeriesType.walking_step_length: AggregationMethod.AVG,
    SeriesType.walking_speed: AggregationMethod.AVG,
    SeriesType.walking_double_support_percentage: AggregationMethod.AVG,
    SeriesType.walking_asymmetry_percentage: AggregationMethod.AVG,
    SeriesType.walking_steadiness: AggregationMethod.AVG,
    SeriesType.stair_descent_speed: AggregationMethod.AVG,
    SeriesType.stair_ascent_speed: AggregationMethod.AVG,
    # ── Activity — Running Metrics ──
    SeriesType.running_power: AggregationMethod.AVG,
    SeriesType.running_speed: AggregationMethod.AVG,
    SeriesType.running_vertical_oscillation: AggregationMethod.AVG,
    SeriesType.running_ground_contact_time: AggregationMethod.AVG,
    SeriesType.running_stride_length: AggregationMethod.AVG,
    # ── Activity — Swimming Metrics ──
    SeriesType.swimming_stroke_count: AggregationMethod.SUM,
    SeriesType.underwater_depth: AggregationMethod.AVG,
    # ── Activity — Generic ──
    SeriesType.cadence: AggregationMethod.AVG,
    SeriesType.power: AggregationMethod.AVG,
    SeriesType.speed: AggregationMethod.AVG,
    SeriesType.workout_effort_score: AggregationMethod.AVG,
    SeriesType.estimated_workout_effort_score: AggregationMethod.AVG,
    # ── Environmental ──
    SeriesType.environmental_audio_exposure: AggregationMethod.AVG,
    SeriesType.headphone_audio_exposure: AggregationMethod.AVG,
    SeriesType.environmental_sound_reduction: AggregationMethod.AVG,
    SeriesType.time_in_daylight: AggregationMethod.SUM,
    SeriesType.water_temperature: AggregationMethod.AVG,
    SeriesType.uv_exposure: AggregationMethod.SUM,
    SeriesType.inhaler_usage: AggregationMethod.SUM,
    SeriesType.weather_temperature: AggregationMethod.AVG,
    SeriesType.weather_humidity: AggregationMethod.AVG,
    # ── Garmin-specific ──
    SeriesType.garmin_stress_level: AggregationMethod.AVG,
    SeriesType.garmin_skin_temperature: AggregationMethod.AVG,
    SeriesType.garmin_fitness_age: AggregationMethod.AVG,
    SeriesType.garmin_body_battery: AggregationMethod.AVG,
    # ── Other ──
    SeriesType.electrodermal_activity: AggregationMethod.AVG,
    SeriesType.push_count: AggregationMethod.SUM,
    SeriesType.atrial_fibrillation_burden: AggregationMethod.SUM,
    SeriesType.insulin_delivery: AggregationMethod.SUM,
    SeriesType.number_of_times_fallen: AggregationMethod.SUM,
    SeriesType.number_of_alcoholic_beverages: AggregationMethod.SUM,
    SeriesType.nike_fuel: AggregationMethod.SUM,
}


def get_aggregation_method(series_type: SeriesType) -> AggregationMethod:
    """Get the aggregation method for a series type.

    Falls back to AVG for unknown types (safe default for rate-like metrics).
    """
    return AGGREGATION_METHOD_BY_TYPE.get(series_type, AggregationMethod.AVG)
