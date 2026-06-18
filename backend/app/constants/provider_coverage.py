"""Declarative provider coverage registry across all data layers.

Each layer corresponds to a different part of the API surface:
- timeseries:     SeriesType samples via /timeseries endpoint
- workout_fields: Fields populated in workout EventRecordDetail via /events
- sleep_fields:   Fields populated in sleep EventRecordDetail via /events
- health_scores:  HealthScoreCategory values via /health-scores endpoint

Update a provider's entry here when new data types are implemented.
Timeseries coverage is derived from grep of each provider's data_247.py
and (for SDK providers) constants/series_types/sdk/metric_types.py.
"""

from app.schemas.enums import SeriesType
from app.schemas.enums.health_score_category import HealthScoreCategory

# ---------------------------------------------------------------------------
# Shared SDK series — Apple/Samsung/Google use the same import pipeline
# ---------------------------------------------------------------------------
_SDK_TIMESERIES: frozenset[SeriesType] = frozenset(
    [
        SeriesType.atrial_fibrillation_burden,
        SeriesType.basal_energy,
        SeriesType.blood_alcohol_content,
        SeriesType.blood_glucose,
        SeriesType.blood_pressure_diastolic,
        SeriesType.blood_pressure_systolic,
        SeriesType.body_fat_mass,
        SeriesType.body_fat_percentage,
        SeriesType.body_mass_index,
        SeriesType.body_temperature,
        SeriesType.cadence,
        SeriesType.distance_cycling,
        SeriesType.distance_downhill_snow_sports,
        SeriesType.distance_other,
        SeriesType.distance_swimming,
        SeriesType.distance_walking_running,
        SeriesType.electrodermal_activity,
        SeriesType.energy,
        SeriesType.environmental_audio_exposure,
        SeriesType.environmental_sound_reduction,
        SeriesType.estimated_workout_effort_score,
        SeriesType.exercise_time,
        SeriesType.flights_climbed,
        SeriesType.forced_expiratory_volume_1,
        SeriesType.forced_vital_capacity,
        SeriesType.headphone_audio_exposure,
        SeriesType.heart_rate,
        SeriesType.heart_rate_recovery_one_minute,
        SeriesType.heart_rate_variability_rmssd,
        SeriesType.heart_rate_variability_sdnn,
        SeriesType.height,
        SeriesType.hydration,
        SeriesType.inhaler_usage,
        SeriesType.insulin_delivery,
        SeriesType.lean_body_mass,
        SeriesType.number_of_alcoholic_beverages,
        SeriesType.number_of_times_fallen,
        SeriesType.oxygen_saturation,
        SeriesType.peak_expiratory_flow_rate,
        SeriesType.peripheral_perfusion_index,
        SeriesType.physical_effort,
        SeriesType.power,
        SeriesType.push_count,
        SeriesType.respiratory_rate,
        SeriesType.resting_heart_rate,
        SeriesType.running_ground_contact_time,
        SeriesType.running_power,
        SeriesType.running_speed,
        SeriesType.running_stride_length,
        SeriesType.running_vertical_oscillation,
        SeriesType.six_minute_walk_test_distance,
        SeriesType.skeletal_muscle_mass,
        SeriesType.sleeping_breathing_disturbances,
        SeriesType.speed,
        SeriesType.stair_ascent_speed,
        SeriesType.stair_descent_speed,
        SeriesType.stand_time,
        SeriesType.steps,
        SeriesType.swimming_stroke_count,
        SeriesType.time_in_daylight,
        SeriesType.uv_exposure,
        SeriesType.vo2_max,
        SeriesType.waist_circumference,
        SeriesType.walking_asymmetry_percentage,
        SeriesType.walking_double_support_percentage,
        SeriesType.walking_heart_rate_average,
        SeriesType.walking_speed,
        SeriesType.walking_steadiness,
        SeriesType.walking_step_length,
        SeriesType.water_temperature,
        SeriesType.weight,
        SeriesType.workout_effort_score,
    ]
)

# ---------------------------------------------------------------------------
# Coverage registry
# ---------------------------------------------------------------------------

type WorkoutFields = frozenset[str]
type SleepFields = frozenset[str]
type HealthScores = frozenset[HealthScoreCategory]
type TimeseriesTypes = frozenset[SeriesType]


class ProviderCoverage:
    __slots__ = ("timeseries", "workout_fields", "sleep_fields", "health_scores")

    def __init__(
        self,
        timeseries: TimeseriesTypes = frozenset(),
        workout_fields: WorkoutFields = frozenset(),
        sleep_fields: SleepFields = frozenset(),
        health_scores: HealthScores = frozenset(),
    ) -> None:
        self.timeseries = timeseries
        self.workout_fields = workout_fields
        self.sleep_fields = sleep_fields
        self.health_scores = health_scores


_FULL_SLEEP_FIELDS: SleepFields = frozenset(
    [
        "sleep_total_duration_minutes",
        "sleep_time_in_bed_minutes",
        "sleep_efficiency_score",
        "sleep_deep_minutes",
        "sleep_rem_minutes",
        "sleep_light_minutes",
        "sleep_awake_minutes",
        "is_nap",
        "sleep_stages",
    ]
)

PROVIDER_COVERAGE: dict[str, ProviderCoverage] = {
    "apple": ProviderCoverage(
        timeseries=_SDK_TIMESERIES,
        # SDK imports whatever the device reports — all workout fields are possible
        workout_fields=frozenset(
            [
                "heart_rate_min",
                "heart_rate_max",
                "heart_rate_avg",
                "steps_count",
                "energy_burned",
                "distance",
                "max_speed",
                "average_speed",
                "average_cadence",
                "moving_time_seconds",
                "total_elevation_gain",
                "elev_high",
                "elev_low",
            ]
        ),
        sleep_fields=_FULL_SLEEP_FIELDS,
    ),
    "samsung": ProviderCoverage(
        timeseries=_SDK_TIMESERIES,
        workout_fields=frozenset(
            [
                "heart_rate_min",
                "heart_rate_max",
                "heart_rate_avg",
                "steps_count",
                "energy_burned",
                "distance",
                "max_speed",
                "average_speed",
                "average_cadence",
                "moving_time_seconds",
                "total_elevation_gain",
                "elev_high",
                "elev_low",
            ]
        ),
        sleep_fields=_FULL_SLEEP_FIELDS,
    ),
    "google": ProviderCoverage(
        timeseries=_SDK_TIMESERIES,
        workout_fields=frozenset(
            [
                "heart_rate_min",
                "heart_rate_max",
                "heart_rate_avg",
                "steps_count",
                "energy_burned",
                "distance",
                "max_speed",
                "average_speed",
                "average_cadence",
                "moving_time_seconds",
                "total_elevation_gain",
                "elev_high",
                "elev_low",
            ]
        ),
        sleep_fields=_FULL_SLEEP_FIELDS,
    ),
    "garmin": ProviderCoverage(
        timeseries=frozenset(
            [
                SeriesType.air_temperature,
                SeriesType.blood_pressure_diastolic,
                SeriesType.blood_pressure_systolic,
                SeriesType.body_fat_percentage,
                SeriesType.body_mass_index,
                SeriesType.cadence,
                SeriesType.distance_walking_running,
                SeriesType.elevation,
                SeriesType.energy,
                SeriesType.flights_climbed,
                SeriesType.garmin_body_battery,
                SeriesType.garmin_fitness_age,
                SeriesType.garmin_stress_level,
                SeriesType.heart_rate,
                SeriesType.heart_rate_variability_rmssd,
                SeriesType.heart_rate_variability_sdnn,
                SeriesType.latitude,
                SeriesType.longitude,
                SeriesType.oxygen_saturation,
                SeriesType.power,
                SeriesType.respiratory_rate,
                SeriesType.resting_heart_rate,
                SeriesType.skin_temperature,
                SeriesType.speed,
                SeriesType.steps,
                SeriesType.vo2_max,
                SeriesType.weight,
            ]
        ),
        workout_fields=frozenset(
            [
                "heart_rate_max",
                "heart_rate_avg",
                "distance",
                "energy_burned",
                "average_cadence",
                "average_speed",
                "total_elevation_gain",
            ]
        ),
        sleep_fields=_FULL_SLEEP_FIELDS,
        health_scores=frozenset(
            [
                HealthScoreCategory.SLEEP,
                HealthScoreCategory.STRESS,
                HealthScoreCategory.BODY_BATTERY,
            ]
        ),
    ),
    "oura": ProviderCoverage(
        timeseries=frozenset(
            [
                SeriesType.breathing_disturbance_index,
                SeriesType.cardiovascular_age,
                SeriesType.distance_walking_running,
                SeriesType.energy,
                SeriesType.heart_rate,
                SeriesType.heart_rate_variability_rmssd,
                SeriesType.height,
                SeriesType.oxygen_saturation,
                SeriesType.respiratory_rate,
                SeriesType.skin_temperature_deviation,
                SeriesType.skin_temperature_trend_deviation,
                SeriesType.steps,
                SeriesType.vo2_max,
                SeriesType.weight,
            ]
        ),
        workout_fields=frozenset(
            [
                "energy_burned",
                "distance",
                "moving_time_seconds",
            ]
        ),
        sleep_fields=_FULL_SLEEP_FIELDS,
        health_scores=frozenset(
            [
                HealthScoreCategory.ACTIVITY,
                HealthScoreCategory.READINESS,
                HealthScoreCategory.SLEEP,
            ]
        ),
    ),
    "polar": ProviderCoverage(
        timeseries=frozenset(
            [
                SeriesType.distance_walking_running,
                SeriesType.energy,
                SeriesType.heart_rate,
                SeriesType.heart_rate_variability_rmssd,
                SeriesType.oxygen_saturation,
                SeriesType.skin_temperature,
                SeriesType.skin_temperature_deviation,
                SeriesType.steps,
            ]
        ),
        workout_fields=frozenset(
            [
                "heart_rate_max",
                "heart_rate_avg",
                "energy_burned",
                "distance",
            ]
        ),
        sleep_fields=frozenset(
            [
                "sleep_total_duration_minutes",
                "sleep_time_in_bed_minutes",
                "sleep_deep_minutes",
                "sleep_rem_minutes",
                "sleep_light_minutes",
                "sleep_awake_minutes",
                "sleep_stages",
            ]
        ),
        health_scores=frozenset(
            [
                HealthScoreCategory.SLEEP,
                HealthScoreCategory.STRAIN,
                HealthScoreCategory.RECOVERY,
                HealthScoreCategory.READINESS,
            ]
        ),
    ),
    "suunto": ProviderCoverage(
        timeseries=frozenset(
            [
                SeriesType.energy,
                SeriesType.heart_rate,
                SeriesType.heart_rate_variability_rmssd,
                SeriesType.oxygen_saturation,
                SeriesType.resting_heart_rate,
                SeriesType.steps,
            ]
        ),
        workout_fields=frozenset(
            [
                "heart_rate_min",
                "heart_rate_max",
                "heart_rate_avg",
                "steps_count",
                "energy_burned",
                "distance",
                "max_speed",
                "max_watts",
                "average_speed",
                "average_watts",
                "moving_time_seconds",
                "total_elevation_gain",
                "elev_high",
                "elev_low",
            ]
        ),
        sleep_fields=frozenset(
            [
                "sleep_total_duration_minutes",
                "sleep_time_in_bed_minutes",
                "sleep_efficiency_score",
                "sleep_deep_minutes",
                "sleep_rem_minutes",
                "sleep_light_minutes",
                "sleep_awake_minutes",
                "is_nap",
            ]
        ),
        health_scores=frozenset([HealthScoreCategory.RECOVERY]),
    ),
    "whoop": ProviderCoverage(
        timeseries=frozenset(
            [
                SeriesType.heart_rate_variability_rmssd,
                SeriesType.height,
                SeriesType.oxygen_saturation,
                SeriesType.resting_heart_rate,
                SeriesType.skin_temperature,
                SeriesType.weight,
            ]
        ),
        workout_fields=frozenset(
            [
                "heart_rate_avg",
                "heart_rate_max",
                "energy_burned",
                "distance",
                "total_elevation_gain",
                "moving_time_seconds",
            ]
        ),
        sleep_fields=frozenset(
            [
                "sleep_total_duration_minutes",
                "sleep_time_in_bed_minutes",
                "sleep_efficiency_score",
                "sleep_deep_minutes",
                "sleep_rem_minutes",
                "sleep_light_minutes",
                "sleep_awake_minutes",
                "is_nap",
            ]
        ),
        health_scores=frozenset(
            [
                HealthScoreCategory.SLEEP,
                HealthScoreCategory.RECOVERY,
                HealthScoreCategory.STRAIN,
            ]
        ),
    ),
    "ultrahuman": ProviderCoverage(
        timeseries=frozenset(
            [
                SeriesType.body_temperature,
                SeriesType.heart_rate,
                SeriesType.heart_rate_variability_sdnn,
                SeriesType.steps,
                SeriesType.vo2_max,
            ]
        ),
        sleep_fields=frozenset(
            [
                "sleep_total_duration_minutes",
                "sleep_time_in_bed_minutes",
                "sleep_efficiency_score",
                "sleep_deep_minutes",
                "sleep_rem_minutes",
                "sleep_light_minutes",
                "sleep_awake_minutes",
                "is_nap",
            ]
        ),
    ),
    "strava": ProviderCoverage(
        workout_fields=frozenset(
            [
                "heart_rate_avg",
                "heart_rate_max",
                "distance",
                "average_speed",
                "max_speed",
                "average_watts",
                "max_watts",
                "total_elevation_gain",
                "elev_high",
                "elev_low",
                "energy_burned",
                "moving_time_seconds",
            ]
        ),
    ),
    "fitbit": ProviderCoverage(
        workout_fields=frozenset(
            [
                "heart_rate_avg",
                "steps_count",
                "energy_burned",
                "distance",
            ]
        ),
    ),
}
