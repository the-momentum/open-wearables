"""Withings workout category id → unified WorkoutType.

Ids come from the Withings ``getworkouts`` category table. Where there is no
exact unified type the nearest is used; the inline comment names the source
activity in those cases. Unlisted ids — "Other", "No activity", and the
lifestyle/chore categories — fall through to ``WorkoutType.OTHER``.
"""

from app.schemas.enums.workout_types import WorkoutType

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
    # 36 "Other" and 128 "No activity" are intentionally omitted (fall through to OTHER)
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
    501: WorkoutType.ARCHERY,
    503: WorkoutType.BASEBALL,  # Baseball Training
    507: WorkoutType.PARAGLIDING,
    508: WorkoutType.DISC_SPORTS,  # Frisbee
    510: WorkoutType.PICKLEBALL,
    513: WorkoutType.DISC_SPORTS,  # Ultimate
    518: WorkoutType.CYCLING,  # Track Cycling
    519: WorkoutType.MULTISPORT,  # Pentathlon
    521: WorkoutType.TRIATHLON,
    523: WorkoutType.MOUNTAIN_BIKING,
    524: WorkoutType.CYCLING,  # Gravel Biking
    525: WorkoutType.CYCLING,  # E-Biking
    526: WorkoutType.MOUNTAIN_BIKING,  # E-Mountain Biking
    527: WorkoutType.CYCLING,  # Handcycling
    529: WorkoutType.BACKCOUNTRY_SKIING,
    530: WorkoutType.CROSS_COUNTRY_SKIING,  # Nordic Skiing
    531: WorkoutType.CROSS_COUNTRY_SKIING,  # Roller Skiing
    532: WorkoutType.RACQUETBALL,
    534: WorkoutType.DANCE,  # Hip Hop
    535: WorkoutType.MARTIAL_ARTS,  # Muaythai
    536: WorkoutType.MARTIAL_ARTS,  # Taekwondo
    537: WorkoutType.MARTIAL_ARTS,  # Judo
    538: WorkoutType.GYMNASTICS,  # Trampoline
    544: WorkoutType.DANCE,  # Breaking
    546: WorkoutType.STRENGTH_TRAINING,  # Crossfit
    547: WorkoutType.INDOOR_CYCLING,  # Spinclass
    548: WorkoutType.CRICKET,
    549: WorkoutType.DANCE,  # Flamenco Dancing
    550: WorkoutType.CARDIO_TRAINING,  # HIIT
    551: WorkoutType.MEDITATION,
    552: WorkoutType.STRETCHING,
    557: WorkoutType.LACROSSE,
    564: WorkoutType.BOWLING,
    566: WorkoutType.WALKING,  # Nordic Walking
    567: WorkoutType.WRESTLING,  # Sumo Wrestling
}


def get_unified_workout_type(category: int) -> WorkoutType:
    """Return the unified WorkoutType for a Withings workout category id.

    Falls back to ``WorkoutType.OTHER`` for any category not in the map.
    """
    return WITHINGS_CATEGORY_MAP.get(category, WorkoutType.OTHER)
