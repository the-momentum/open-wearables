"""Unified series type definitions for time-series data.

This module contains:
- SeriesType enum with all supported metric types (internal use)
- BiometricSeriesType enum for /timeseries/biometrics endpoint
- ActivitySeriesType enum for /timeseries/activity endpoint
- Stable integer IDs for database persistence
- Unit definitions for each series type
- Helper functions for ID/enum conversions

IMPORTANT: Never change existing IDs - only add new ones. IDs are persisted in the database.
"""

from enum import Enum


class SeriesType(str, Enum):
    """All supported time-series metric types (internal use - DB operations)."""

    # =========================================================================
    # BIOMETRICS - Heart & Cardiovascular (IDs 1-19)
    # =========================================================================
    heart_rate = "heart_rate"
    resting_heart_rate = "resting_heart_rate"
    heart_rate_variability_sdnn = "heart_rate_variability_sdnn"
    heart_rate_recovery_one_minute = "heart_rate_recovery_one_minute"
    walking_heart_rate_average = "walking_heart_rate_average"

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


class BiometricSeriesType(str, Enum):
    """Biometric time-series types for /timeseries/biometrics endpoint."""

    # Heart & Cardiovascular
    heart_rate = "heart_rate"
    resting_heart_rate = "resting_heart_rate"
    heart_rate_variability_sdnn = "heart_rate_variability_sdnn"
    heart_rate_recovery_one_minute = "heart_rate_recovery_one_minute"
    walking_heart_rate_average = "walking_heart_rate_average"

    # Blood & Respiratory
    oxygen_saturation = "oxygen_saturation"
    blood_glucose = "blood_glucose"
    blood_pressure_systolic = "blood_pressure_systolic"
    blood_pressure_diastolic = "blood_pressure_diastolic"
    respiratory_rate = "respiratory_rate"
    sleeping_breathing_disturbances = "sleeping_breathing_disturbances"

    # Body Composition
    height = "height"
    weight = "weight"
    body_fat_percentage = "body_fat_percentage"
    body_mass_index = "body_mass_index"
    lean_body_mass = "lean_body_mass"
    body_temperature = "body_temperature"

    # Fitness Metrics
    vo2_max = "vo2_max"
    six_minute_walk_test_distance = "six_minute_walk_test_distance"


class ActivitySeriesType(str, Enum):
    """Activity time-series types for /timeseries/activity endpoint."""

    # Basic Activity
    steps = "steps"
    energy = "energy"
    basal_energy = "basal_energy"
    stand_time = "stand_time"
    exercise_time = "exercise_time"
    physical_effort = "physical_effort"
    flights_climbed = "flights_climbed"

    # Distance
    distance_walking_running = "distance_walking_running"
    distance_cycling = "distance_cycling"
    distance_swimming = "distance_swimming"
    distance_downhill_snow_sports = "distance_downhill_snow_sports"

    # Walking Metrics
    walking_step_length = "walking_step_length"
    walking_speed = "walking_speed"
    walking_double_support_percentage = "walking_double_support_percentage"
    walking_asymmetry_percentage = "walking_asymmetry_percentage"
    walking_steadiness = "walking_steadiness"
    stair_descent_speed = "stair_descent_speed"
    stair_ascent_speed = "stair_ascent_speed"

    # Running Metrics
    running_power = "running_power"
    running_speed = "running_speed"
    running_vertical_oscillation = "running_vertical_oscillation"
    running_ground_contact_time = "running_ground_contact_time"
    running_stride_length = "running_stride_length"

    # Swimming Metrics
    swimming_stroke_count = "swimming_stroke_count"

    # Generic
    cadence = "cadence"
    power = "power"


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
]

# =============================================================================
# CATEGORY GROUPINGS (for API endpoints)
# =============================================================================

# Biometric types - for /timeseries/biometrics endpoint
BIOMETRIC_SERIES_TYPES: set[SeriesType] = {
    # Heart & Cardiovascular
    SeriesType.heart_rate,
    SeriesType.resting_heart_rate,
    SeriesType.heart_rate_variability_sdnn,
    SeriesType.heart_rate_recovery_one_minute,
    SeriesType.walking_heart_rate_average,
    # Blood & Respiratory
    SeriesType.oxygen_saturation,
    SeriesType.blood_glucose,
    SeriesType.blood_pressure_systolic,
    SeriesType.blood_pressure_diastolic,
    SeriesType.respiratory_rate,
    SeriesType.sleeping_breathing_disturbances,
    # Body Composition
    SeriesType.height,
    SeriesType.weight,
    SeriesType.body_fat_percentage,
    SeriesType.body_mass_index,
    SeriesType.lean_body_mass,
    SeriesType.body_temperature,
    # Fitness Metrics
    SeriesType.vo2_max,
    SeriesType.six_minute_walk_test_distance,
}

# Activity types - for /timeseries/activity endpoint
ACTIVITY_SERIES_TYPES: set[SeriesType] = {
    # Basic
    SeriesType.steps,
    SeriesType.energy,
    SeriesType.basal_energy,
    SeriesType.stand_time,
    SeriesType.exercise_time,
    SeriesType.physical_effort,
    SeriesType.flights_climbed,
    # Distance
    SeriesType.distance_walking_running,
    SeriesType.distance_cycling,
    SeriesType.distance_swimming,
    SeriesType.distance_downhill_snow_sports,
    # Walking Metrics
    SeriesType.walking_step_length,
    SeriesType.walking_speed,
    SeriesType.walking_double_support_percentage,
    SeriesType.walking_asymmetry_percentage,
    SeriesType.walking_steadiness,
    SeriesType.stair_descent_speed,
    SeriesType.stair_ascent_speed,
    # Running Metrics
    SeriesType.running_power,
    SeriesType.running_speed,
    SeriesType.running_vertical_oscillation,
    SeriesType.running_ground_contact_time,
    SeriesType.running_stride_length,
    # Swimming Metrics
    SeriesType.swimming_stroke_count,
    # Generic
    SeriesType.cadence,
    SeriesType.power,
}

# Environmental types - could be separate endpoint or included in activity
ENVIRONMENTAL_SERIES_TYPES: set[SeriesType] = {
    SeriesType.environmental_audio_exposure,
    SeriesType.headphone_audio_exposure,
    SeriesType.environmental_sound_reduction,
    SeriesType.time_in_daylight,
    SeriesType.water_temperature,
}

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


def is_biometric_type(series_type: SeriesType) -> bool:
    """Check if a series type belongs to biometrics category."""
    return series_type in BIOMETRIC_SERIES_TYPES


def is_activity_type(series_type: SeriesType) -> bool:
    """Check if a series type belongs to activity category."""
    return series_type in ACTIVITY_SERIES_TYPES


def is_environmental_type(series_type: SeriesType) -> bool:
    """Check if a series type belongs to environmental category."""
    return series_type in ENVIRONMENTAL_SERIES_TYPES


def biometric_to_series_type(biometric_type: BiometricSeriesType) -> SeriesType:
    """Convert BiometricSeriesType to SeriesType for internal operations."""
    return SeriesType(biometric_type.value)


def activity_to_series_type(activity_type: ActivitySeriesType) -> SeriesType:
    """Convert ActivitySeriesType to SeriesType for internal operations."""
    return SeriesType(activity_type.value)
