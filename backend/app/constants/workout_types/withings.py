"""Withings workout-category integer → unified WorkoutType map.

Source of truth for the integers:
https://developer.withings.com/developer-guide/v3/data-api/all-available-health-data/workout/

Withings exposes ~70 categories. We map the common ones explicitly and
bucket the long tail under ``WorkoutType.OTHER`` so we don't lose data.
"""

from app.schemas.enums import WorkoutType

# Format: { withings_category_int: WorkoutType }
WITHINGS_CATEGORY_TO_WORKOUT_TYPE: dict[int, WorkoutType] = {
    # Walking / running / hiking
    1: WorkoutType.WALKING,
    2: WorkoutType.RUNNING,
    3: WorkoutType.HIKING,
    46: WorkoutType.TREADMILL,  # indoor running

    # Cycling
    6: WorkoutType.CYCLING,
    48: WorkoutType.INDOOR_CYCLING,
    192: WorkoutType.CYCLING,  # cross fit (no real match — bucket as cycling? actually cross-fit is conditioning, fall through)

    # Water
    7: WorkoutType.SWIMMING,
    8: WorkoutType.SURFING,
    9: WorkoutType.KITESURFING,
    10: WorkoutType.WINDSURFING,
    11: WorkoutType.SURFING,  # bodyboard — close enough
    25: WorkoutType.WATER_POLO,
    36: WorkoutType.ROWING,
    187: WorkoutType.STAND_UP_PADDLEBOARDING,

    # Racquet
    12: WorkoutType.TENNIS,
    13: WorkoutType.TABLE_TENNIS,
    14: WorkoutType.SQUASH,
    15: WorkoutType.BADMINTON,

    # Strength / gym
    16: WorkoutType.STRENGTH_TRAINING,  # lift weights
    17: WorkoutType.CARDIO_TRAINING,    # calisthenics
    18: WorkoutType.ELLIPTICAL,
    196: WorkoutType.STRENGTH_TRAINING,  # weight training (gym)

    # Mind-body
    19: WorkoutType.PILATES,
    28: WorkoutType.YOGA,

    # Team sports
    20: WorkoutType.BASKETBALL,
    21: WorkoutType.SOCCER,
    22: WorkoutType.AMERICAN_FOOTBALL,
    23: WorkoutType.RUGBY,
    24: WorkoutType.VOLLEYBALL,
    40: WorkoutType.BASEBALL,
    41: WorkoutType.HANDBALL,
    42: WorkoutType.HOCKEY,
    43: WorkoutType.HOCKEY,  # ice-hockey — closest unified type

    # Combat
    30: WorkoutType.BOXING,
    31: WorkoutType.MARTIAL_ARTS,  # fencing
    32: WorkoutType.WRESTLING,
    33: WorkoutType.MARTIAL_ARTS,

    # Winter
    34: WorkoutType.ALPINE_SKIING,
    35: WorkoutType.SNOWBOARDING,
    191: WorkoutType.CROSS_COUNTRY_SKIING,
    45: WorkoutType.ICE_SKATING,

    # Other
    4: WorkoutType.SKATING,
    5: WorkoutType.CYCLING,  # BMX — bucket as cycling
    26: WorkoutType.HORSEBACK_RIDING,
    27: WorkoutType.GOLF,
    29: WorkoutType.DANCE,
    39: WorkoutType.AEROBICS,  # zumba
    44: WorkoutType.ROCK_CLIMBING,
    47: WorkoutType.MULTISPORT,
}


def get_unified_workout_type(category: int | None) -> WorkoutType:
    """Return the WorkoutType for a Withings category int, OTHER if unmapped."""
    if category is None:
        return WorkoutType.OTHER
    return WITHINGS_CATEGORY_TO_WORKOUT_TYPE.get(category, WorkoutType.OTHER)
