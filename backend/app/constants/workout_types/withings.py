"""Map Withings OpenAPI workout categories to unified workout types."""

from app.schemas.enums.workout_types import WorkoutType

OFFICIAL_WITHINGS_CATEGORY_IDS = frozenset(
    {
        *range(1, 37),
        128,
        187,
        188,
        *range(191, 197),
        272,
        *range(306, 309),
        *range(455, 458),
        *range(490, 533),
        *range(534, 569),
    }
)

WITHINGS_CATEGORY_MAP: dict[int, WorkoutType] = {
    1: WorkoutType.WALKING,
    2: WorkoutType.RUNNING,
    3: WorkoutType.HIKING,
    4: WorkoutType.SKATING,
    5: WorkoutType.CYCLING,  # BMX
    6: WorkoutType.CYCLING,  # Bicycling
    7: WorkoutType.SWIMMING,
    8: WorkoutType.SURFING,
    9: WorkoutType.KITESURFING,
    10: WorkoutType.WINDSURFING,
    11: WorkoutType.SURFING,  # Bodyboard
    12: WorkoutType.TENNIS,
    13: WorkoutType.TABLE_TENNIS,
    14: WorkoutType.SQUASH,
    15: WorkoutType.BADMINTON,
    16: WorkoutType.STRENGTH_TRAINING,  # Lift weights
    17: WorkoutType.STRENGTH_TRAINING,  # Fitness
    18: WorkoutType.ELLIPTICAL,
    19: WorkoutType.PILATES,
    20: WorkoutType.BASKETBALL,
    21: WorkoutType.SOCCER,
    22: WorkoutType.AMERICAN_FOOTBALL,  # Football (soccer is 21)
    23: WorkoutType.RUGBY,
    24: WorkoutType.VOLLEYBALL,
    25: WorkoutType.WATER_POLO,
    26: WorkoutType.HORSEBACK_RIDING,
    27: WorkoutType.GOLF,
    28: WorkoutType.YOGA,
    29: WorkoutType.DANCE,
    30: WorkoutType.BOXING,
    31: WorkoutType.FENCING,
    32: WorkoutType.WRESTLING,
    33: WorkoutType.MARTIAL_ARTS,
    34: WorkoutType.ALPINE_SKIING,  # Skiing
    35: WorkoutType.SNOWBOARDING,
    36: WorkoutType.GENERIC,  # Withings' own "Other", not an unmapped id
    187: WorkoutType.ROWING,
    188: WorkoutType.DANCE,  # Zumba
    191: WorkoutType.BASEBALL,
    192: WorkoutType.HANDBALL,
    193: WorkoutType.HOCKEY,
    194: WorkoutType.HOCKEY,  # Ice hockey
    195: WorkoutType.ROCK_CLIMBING,
    196: WorkoutType.ICE_SKATING,
    272: WorkoutType.MULTISPORT,
    306: WorkoutType.WALKING,  # Indoor walk
    307: WorkoutType.TREADMILL,  # Indoor running
    308: WorkoutType.INDOOR_CYCLING,
    455: WorkoutType.STAND_UP_PADDLEBOARDING,
    456: WorkoutType.PADEL,
    457: WorkoutType.GAMING,
    490: WorkoutType.VOLLEYBALL,  # Beach volleyball
    491: WorkoutType.STAIR_CLIMBING,  # Stair Stepper
    492: WorkoutType.SKATEBOARDING,
    493: WorkoutType.PARKOUR,
    494: WorkoutType.KAYAKING,
    495: WorkoutType.CANOEING,
    496: WorkoutType.SAILING,
    497: WorkoutType.FISHING,
    498: WorkoutType.TRAIL_RUNNING,
    499: WorkoutType.SNOWSHOEING,
    500: WorkoutType.SPORT,  # Paintball
    501: WorkoutType.ARCHERY,
    502: WorkoutType.DIVING,
    503: WorkoutType.BASEBALL,  # Baseball Training
    504: WorkoutType.MULTISPORT,  # Biathlon: skiing plus shooting, as Pentathlon below
    505: WorkoutType.SPORT,  # Bocce; BOWLING carries ten-pin semantics, not boules
    506: WorkoutType.SPORT,  # Pétanque; see Bocce
    507: WorkoutType.PARAGLIDING,
    508: WorkoutType.DISC_SPORTS,  # Frisbee
    509: WorkoutType.SPORT,  # Skydiving; PARAGLIDING is a different discipline
    510: WorkoutType.PICKLEBALL,
    511: WorkoutType.SPORT,  # Cornhole
    512: WorkoutType.SPORT,  # Dodgeball
    513: WorkoutType.DISC_SPORTS,  # Ultimate
    514: WorkoutType.SPORT,  # Teqball
    515: WorkoutType.WHEELCHAIR,
    516: WorkoutType.WHEELCHAIR,
    517: WorkoutType.SPORT,  # Athletics: track and field umbrella, so not RUNNING
    518: WorkoutType.CYCLING,  # Track Cycling
    519: WorkoutType.MULTISPORT,  # Pentathlon
    520: WorkoutType.SPORT,  # Sport Shooting; neither ARCHERY nor HUNTING
    521: WorkoutType.TRIATHLON,
    522: WorkoutType.DIVING,
    523: WorkoutType.MOUNTAIN_BIKING,
    524: WorkoutType.CYCLING,  # Gravel Biking
    525: WorkoutType.E_BIKING,
    526: WorkoutType.MOUNTAIN_BIKING,  # E-Mountain Biking
    527: WorkoutType.CYCLING,  # Handcycling
    528: WorkoutType.CYCLING,  # Velomobile
    529: WorkoutType.BACKCOUNTRY_SKIING,
    530: WorkoutType.CROSS_COUNTRY_SKIING,  # Nordic Skiing
    531: WorkoutType.CROSS_COUNTRY_SKIING,  # Roller Skiing
    532: WorkoutType.RACQUETBALL,
    534: WorkoutType.DANCE,  # Hip Hop
    535: WorkoutType.MARTIAL_ARTS,  # Muaythai
    536: WorkoutType.MARTIAL_ARTS,  # Taekwondo
    537: WorkoutType.MARTIAL_ARTS,  # Judo
    538: WorkoutType.GYMNASTICS,  # Trampoline
    539: WorkoutType.PARA_SPORTS,  # Standing Frame: adaptive activity with no modality of its own
    540: WorkoutType.STRENGTH_TRAINING,  # Seated Strenght [sic]
    541: WorkoutType.CARDIO_TRAINING,  # Seated Cardio
    542: WorkoutType.WALKING,  # Walk With Walker
    543: WorkoutType.WALKING,  # Walk With Cane
    544: WorkoutType.DANCE,  # Breaking
    545: WorkoutType.CHORES,
    546: WorkoutType.STRENGTH_TRAINING,  # Crossfit
    547: WorkoutType.INDOOR_CYCLING,  # Spinclass
    548: WorkoutType.CRICKET,
    549: WorkoutType.DANCE,  # Flamenco Dancing
    550: WorkoutType.CARDIO_TRAINING,  # HIIT
    551: WorkoutType.MEDITATION,
    552: WorkoutType.STRETCHING,
    553: WorkoutType.CHORES,
    554: WorkoutType.CHORES,
    555: WorkoutType.LIFESTYLE,  # Public Speaking
    556: WorkoutType.SPORT,  # Spikeball
    557: WorkoutType.LACROSSE,
    558: WorkoutType.WALKING,  # Baby Wearing
    559: WorkoutType.WALKING,  # Dog Walking
    560: WorkoutType.MEDITATION,  # Breathing excercises [sic]
    561: WorkoutType.STRETCHING,  # Balance Drills: low-intensity mobility work
    562: WorkoutType.WALKING,  # Pushing a Stroller
    563: WorkoutType.WALKING,  # Toddler Wearing
    564: WorkoutType.BOWLING,
    565: WorkoutType.SPORT,  # Lasertag
    566: WorkoutType.WALKING,  # Nordic Walking
    567: WorkoutType.WRESTLING,  # Sumo Wrestling
    568: WorkoutType.CHORES,
}

# Catalogued categories that intentionally lack a canonical workout type.
DEFERRED_WITHINGS_CATEGORIES: dict[int, str] = {
    128: "'No activity' marker rather than a workout; such records are dropped before normalization",
}


def get_unified_workout_type(category: int) -> WorkoutType:
    """Return the unified WorkoutType for a Withings workout category id.

    Falls back to ``WorkoutType.OTHER`` for any id outside the map: the deferred
    catalogue entries and categories Withings does not document.
    """
    return WITHINGS_CATEGORY_MAP.get(category, WorkoutType.OTHER)
