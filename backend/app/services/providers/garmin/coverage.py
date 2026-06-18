from app.schemas.enums import SeriesType
from app.schemas.enums.health_score_category import HealthScoreCategory

TIMESERIES: frozenset[SeriesType] = frozenset([
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
])

WORKOUT_FIELDS: frozenset[str] = frozenset([
    "heart_rate_max",
    "heart_rate_avg",
    "distance",
    "energy_burned",
    "average_cadence",
    "average_speed",
    "total_elevation_gain",
])

SLEEP_FIELDS: frozenset[str] = frozenset([
    "sleep_total_duration_minutes",
    "sleep_time_in_bed_minutes",
    "sleep_efficiency_score",
    "sleep_deep_minutes",
    "sleep_rem_minutes",
    "sleep_light_minutes",
    "sleep_awake_minutes",
    "is_nap",
    "sleep_stages",
])

HEALTH_SCORES: frozenset[HealthScoreCategory] = frozenset([
    HealthScoreCategory.SLEEP,
    HealthScoreCategory.STRESS,
    HealthScoreCategory.BODY_BATTERY,
])
