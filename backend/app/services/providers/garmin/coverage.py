from app.schemas.enums import SeriesType
from app.schemas.enums.health_score_category import HealthScoreCategory

# Timeseries mappings (handler key → SeriesType) consumed directly by data_247.py.

# activityDetails.samples[] field → SeriesType (also reused for FIT-file parsing).
# Note: Garmin API uses "Celcius" (sic) — matches the actual JSON field name.
ACTIVITY_SAMPLE_SERIES: list[tuple[str, SeriesType]] = [
    ("heartRate", SeriesType.heart_rate),
    ("speedMetersPerSecond", SeriesType.speed),
    ("stepsPerMinute", SeriesType.cadence),
    ("powerInWatts", SeriesType.power),
    ("elevationInMeters", SeriesType.elevation),
    ("latitudeInDegree", SeriesType.latitude),
    ("longitudeInDegree", SeriesType.longitude),
    ("airTemperatureCelcius", SeriesType.air_temperature),
]

# Daily summary field → SeriesType (/wellness-api/rest/dailies).
DAILIES_SERIES: list[tuple[str, SeriesType]] = [
    ("steps", SeriesType.steps),
    ("active_calories", SeriesType.energy),
    ("resting_heart_rate", SeriesType.resting_heart_rate),
    ("floors_climbed", SeriesType.flights_climbed),
    ("distance_meters", SeriesType.distance_walking_running),
]

# Epoch sample category → SeriesType (/wellness-api/rest/epochs).
EPOCHS_SERIES: dict[str, SeriesType] = {
    "heart_rate": SeriesType.heart_rate,
    "steps": SeriesType.steps,
    "energy": SeriesType.energy,
}

TIMESERIES: frozenset[SeriesType] = frozenset(
    {
        *(st for _, st in ACTIVITY_SAMPLE_SERIES),  # /wellness-api/rest/activities (activityDetails + FIT)
        *(st for _, st in DAILIES_SERIES),  # /wellness-api/rest/dailies
        *EPOCHS_SERIES.values(),  # /wellness-api/rest/epochs
        SeriesType.weight,  # /wellness-api/rest/bodyComps
        SeriesType.body_fat_percentage,  # /wellness-api/rest/bodyComps
        SeriesType.body_mass_index,  # /wellness-api/rest/bodyComps
        SeriesType.skeletal_muscle_mass,  # /wellness-api/rest/bodyComps
        SeriesType.heart_rate_variability_rmssd,  # /wellness-api/rest/hrv + healthSnapshot
        SeriesType.heart_rate_variability_sdnn,  # /wellness-api/rest/healthSnapshot
        SeriesType.garmin_stress_level,  # /wellness-api/rest/stressDetails + healthSnapshot
        SeriesType.garmin_body_battery,  # /wellness-api/rest/stressDetails
        SeriesType.respiratory_rate,  # /wellness-api/rest/respiration + healthSnapshot
        SeriesType.oxygen_saturation,  # /wellness-api/rest/pulseOx + healthSnapshot
        SeriesType.blood_pressure_systolic,  # /wellness-api/rest/bloodPressures
        SeriesType.blood_pressure_diastolic,  # /wellness-api/rest/bloodPressures
        SeriesType.vo2_max,  # /wellness-api/rest/userMetrics
        SeriesType.garmin_fitness_age,  # /wellness-api/rest/userMetrics
        SeriesType.skin_temperature,  # /wellness-api/rest/skinTemp
    }
)

# EventRecordDetail fields populated by workouts.py and data_247.py (workout records).
WORKOUT_FIELDS: frozenset[str] = frozenset(
    {
        "heart_rate_min",
        "heart_rate_max",
        "heart_rate_avg",
        "steps_count",
        "energy_burned",
        "distance",
        "average_cadence",
        "average_speed",
        "total_elevation_gain",
    }
)

# EventRecordDetail fields populated by data_247.py (sleep records).
SLEEP_FIELDS: frozenset[str] = frozenset(
    {
        "sleep_total_duration_minutes",
        "sleep_time_in_bed_minutes",
        "sleep_efficiency_score",
        "sleep_deep_minutes",
        "sleep_rem_minutes",
        "sleep_light_minutes",
        "sleep_awake_minutes",
        "is_nap",
        "sleep_stages",
    }
)

HEALTH_SCORES: frozenset[HealthScoreCategory] = frozenset(
    {
        HealthScoreCategory.SLEEP,
        HealthScoreCategory.STRESS,
        HealthScoreCategory.BODY_BATTERY,
    }
)
