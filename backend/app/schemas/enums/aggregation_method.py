from enum import Enum

from .series_types import SeriesType


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
