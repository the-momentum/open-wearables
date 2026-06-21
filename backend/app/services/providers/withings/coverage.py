from app.schemas.enums import SeriesType
from app.schemas.enums.health_score_category import HealthScoreCategory

# Withings ``getmeas`` type code -> unified SeriesType. Keep this list limited
# to direct semantic + unit matches from official Withings API/OpenAPI docs.
MEASURE_TYPE_MAP: dict[int, SeriesType] = {
    1: SeriesType.weight,
    4: SeriesType.height,
    5: SeriesType.lean_body_mass,
    6: SeriesType.body_fat_percentage,
    8: SeriesType.body_fat_mass,
    9: SeriesType.blood_pressure_diastolic,
    10: SeriesType.blood_pressure_systolic,
    11: SeriesType.heart_rate,
    12: SeriesType.body_temperature,
    54: SeriesType.oxygen_saturation,
    71: SeriesType.body_temperature,
    73: SeriesType.skin_temperature,
    76: SeriesType.skeletal_muscle_mass,
    # Official notification categories document glucose as meastype 119 (mg/dL);
    # the current OpenAPI getmeas parameter table omits it.
    119: SeriesType.blood_glucose,
    123: SeriesType.vo2_max,
    155: SeriesType.cardiovascular_age,
}

# Withings ``getmeas`` types we deliberately leave unmapped, with the reason.
# Kept as data (not commented-out code) so the decision is recorded without dead
# code and a guard test can assert it never overlaps MEASURE_TYPE_MAP. Adding a
# core SeriesType for any of these is an append-only model change to agree first.
# HRV is likewise absent until its getmeas meastype is confirmed from a real
# response.
DEFERRED_MEASURE_TYPES: dict[int, str] = {
    77: "body-water mass (kg); core hydration is intake (mL)",
    88: "bone mass; no core series type",
    91: "pulse wave velocity; no core series type",
    130: "AFib classification, not burden/count",
    135: "QRS interval duration; no core series type",
    136: "PR interval duration; no core series type",
    137: "QT interval duration; no core series type",
    138: "corrected QT interval duration; no core series type",
    139: "AFib result from PPG; classification, not a core series",
    167: "nerve health conductance (feet); no core series type",
    168: "extracellular water (kg); not the core mL intake series",
    169: "intracellular water (kg); not the core mL intake series",
    170: "visceral fat; no core series type",
    173: "segmental fat-free mass; no core series type",
    174: "segmental fat mass; no core series type",
    175: "segmental muscle mass; no core series type",
    196: "feet-specific EDA/ESC, not the core electrodermal count",
    226: "BMR rate, not basal energy expenditure",
    227: "metabolic age, not cardiovascular age",
    229: "electrochemical skin conductance; no core series type",
}

# Withings ``getactivity`` field -> unified SeriesType.
ACTIVITY_FIELD_MAP: dict[str, SeriesType] = {
    "steps": SeriesType.steps,
    "distance": SeriesType.distance_walking_running,
    "calories": SeriesType.energy,
    "totalcalories": SeriesType.basal_energy,
}

TIMESERIES: frozenset[SeriesType] = frozenset(
    {
        *MEASURE_TYPE_MAP.values(),
        *ACTIVITY_FIELD_MAP.values(),
    }
)

WORKOUT_FIELDS: frozenset[str] = frozenset(
    {
        "heart_rate_avg",
        "heart_rate_min",
        "heart_rate_max",
        "steps_count",
        "energy_burned",
        "distance",
        "total_elevation_gain",
    }
)

SLEEP_FIELDS: frozenset[str] = frozenset(
    {
        "sleep_total_duration_minutes",
        "sleep_time_in_bed_minutes",
        "sleep_efficiency_score",
        "sleep_deep_minutes",
        "sleep_light_minutes",
        "sleep_rem_minutes",
        "sleep_awake_minutes",
        "is_nap",
    }
)

# Withings sleep_score is requested but not persisted as a HealthScore yet.
HEALTH_SCORES: frozenset[HealthScoreCategory] = frozenset()
