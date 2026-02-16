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

    # =========================================================================
    # ACTIVITY - Distance (IDs 100-119)
    # =========================================================================
    distance_walking_running = "distance_walking_running"
    distance_cycling = "distance_cycling"
    distance_swimming = "distance_swimming"
    distance_downhill_snow_sports = "distance_downhill_snow_sports"

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

    # =========================================================================
    # ACTIVITY - Generic (IDs 180-199)
    # =========================================================================
    cadence = "cadence"
    power = "power"

    # =========================================================================
    # ENVIRONMENTAL (IDs 200-219)
    # =========================================================================
    environmental_audio_exposure = "environmental_audio_exposure"
    headphone_audio_exposure = "headphone_audio_exposure"
    environmental_sound_reduction = "environmental_sound_reduction"
    time_in_daylight = "time_in_daylight"
    water_temperature = "water_temperature"

    # =========================================================================
    # GARMIN-SPECIFIC METRICS (IDs 220-239)
    # =========================================================================
    garmin_stress_level = "garmin_stress_level"  # Garmin stress score (1-100)
    garmin_skin_temperature = "garmin_skin_temperature"  # Skin temp deviation from baseline
    garmin_fitness_age = "garmin_fitness_age"  # Garmin fitness age estimate
    garmin_body_battery = "garmin_body_battery"  # Garmin body battery (0-100)


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
    # -------------------------------------------------------------------------
    # ACTIVITY - Distance (IDs 100-119)
    # -------------------------------------------------------------------------
    (100, SeriesType.distance_walking_running, "meters"),
    (101, SeriesType.distance_cycling, "meters"),
    (102, SeriesType.distance_swimming, "meters"),
    (103, SeriesType.distance_downhill_snow_sports, "meters"),
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
    # -------------------------------------------------------------------------
    # ACTIVITY - Generic (IDs 180-199)
    # -------------------------------------------------------------------------
    (180, SeriesType.cadence, "rpm"),
    (181, SeriesType.power, "watts"),
    # -------------------------------------------------------------------------
    # ENVIRONMENTAL (IDs 200-219)
    # -------------------------------------------------------------------------
    (200, SeriesType.environmental_audio_exposure, "dB"),
    (201, SeriesType.headphone_audio_exposure, "dB"),
    (202, SeriesType.environmental_sound_reduction, "dB"),
    (203, SeriesType.time_in_daylight, "minutes"),
    (204, SeriesType.water_temperature, "celsius"),
    # -------------------------------------------------------------------------
    # GARMIN-SPECIFIC METRICS (IDs 220-239)
    # -------------------------------------------------------------------------
    (220, SeriesType.garmin_stress_level, "score"),
    (221, SeriesType.garmin_skin_temperature, "celsius"), # kept for backwards compatibility
    (222, SeriesType.garmin_fitness_age, "years"),
    (223, SeriesType.garmin_body_battery, "percent"),
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
