from decimal import Decimal

from app.schemas.enums import SeriesType
from app.schemas.enums.health_score_category import HealthScoreCategory

# Withings ``/measure?action=getmeas`` type code -> unified SeriesType. Keep
# this list limited to direct semantic + unit matches from official Withings
# API/OpenAPI docs.
MEASURE_TYPE_MAP: dict[int, SeriesType] = {
    1: SeriesType.weight,
    4: SeriesType.height,
    5: SeriesType.lean_body_mass,
    6: SeriesType.body_fat_percentage,
    8: SeriesType.body_fat_mass,
    9: SeriesType.blood_pressure_diastolic,
    10: SeriesType.blood_pressure_systolic,
    11: SeriesType.heart_rate,
    54: SeriesType.oxygen_saturation,
    71: SeriesType.body_temperature,
    73: SeriesType.skin_temperature,
    76: SeriesType.skeletal_muscle_mass,
    77: SeriesType.body_water_mass,
    88: SeriesType.bone_mass,
    91: SeriesType.withings_pulse_wave_velocity,
    # Notification docs assign glucose meastype 119; the getmeas parameter table omits it.
    119: SeriesType.blood_glucose,
    123: SeriesType.vo2_max,
    155: SeriesType.cardiovascular_age,
    227: SeriesType.withings_metabolic_age,
}

# A few measures arrive in a different unit than the unified SeriesType. After
# decoding (value × 10^unit), multiply by this factor to match OW units.
#   meastype 4 (height): Withings reports metres; OW ``height`` is centimetres.
MEASURE_UNIT_FACTOR: dict[int, Decimal] = {
    4: Decimal(100),
}

# Withings ``getmeas`` types intentionally lacking a direct canonical series.
DEFERRED_MEASURE_TYPES: dict[int, str] = {
    12: (
        "context-dependent generic temperature; observed as WS-50/Home environmental temperature, with conflicting "
        "legacy thermometer evidence; requires device-aware mapping"
    ),
    130: "AFib classification, not burden/count",
    135: "QRS interval duration; no core series type",
    136: "PR interval duration; no core series type",
    137: "QT interval duration; no core series type",
    138: "corrected QT interval duration; no core series type",
    139: "AFib result from PPG; classification, not a core series",
    140: "vascular age contract conflict; deferred/source-gated and not requested",
    158: "left-foot Nerve Health Score; no core series type",
    159: "right-foot Nerve Health Score; no core series type",
    167: (
        "source-contract conflict: generic OpenAPI conductance wording versus dedicated Body Scan maximum Nerve "
        "Health Score semantics"
    ),
    168: "extracellular water (kg); not the core mL intake series",
    169: "intracellular water (kg); not the core mL intake series",
    170: "visceral fat; no core series type",
    173: "segmental fat-free mass; no core series type",
    174: "segmental fat mass; no core series type",
    175: "segmental muscle mass; no core series type",
    196: "Nerve Response Score; no core series type",
    226: "BMR rate, not basal energy expenditure",
    229: "electrochemical skin conductance; no core series type",
}

# Withings ``/v2/measure?action=getactivity`` field -> unified SeriesType.
ACTIVITY_FIELD_MAP: dict[str, SeriesType] = {
    "steps": SeriesType.steps,
    "distance": SeriesType.distance_walking_running,
    "calories": SeriesType.energy,
}

TIMESERIES: frozenset[SeriesType] = frozenset(
    {
        *MEASURE_TYPE_MAP.values(),
        *ACTIVITY_FIELD_MAP.values(),
        SeriesType.basal_energy,
    }
)

# EventRecordDetail fields populated by ``/v2/measure?action=getworkouts``.
WORKOUT_FIELDS: frozenset[str] = frozenset(
    {
        "heart_rate_avg",
        "heart_rate_min",
        "heart_rate_max",
        "steps_count",
        "energy_burned",
        "distance",
    }
)

# EventRecordDetail fields populated by ``/v2/sleep?action=getsummary``.
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

# sleep_score is excluded because it has no HealthScore mapping.
HEALTH_SCORES: frozenset[HealthScoreCategory] = frozenset()
