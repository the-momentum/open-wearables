"""Oura Ring workout type mappings.

Oura uses lowercase activity strings (e.g. "running", "cycling").
Reference: https://cloud.ouraring.com/v2/docs#tag/Workout
"""

from app.schemas.workout_types import WorkoutType

# (oura_activity_string, unified_type)
OURA_WORKOUT_TYPE_MAPPINGS: list[tuple[str, WorkoutType]] = [
    # Running & Walking
    ("running", WorkoutType.RUNNING),
    ("trail_running", WorkoutType.TRAIL_RUNNING),
    ("walking", WorkoutType.WALKING),
    ("hiking", WorkoutType.HIKING),
    # Cycling
    ("cycling", WorkoutType.CYCLING),
    ("mountain_biking", WorkoutType.MOUNTAIN_BIKING),
    ("indoor_cycling", WorkoutType.INDOOR_CYCLING),
    # Swimming & Water Sports
    ("swimming", WorkoutType.SWIMMING),
    ("rowing", WorkoutType.ROWING),
    ("kayaking", WorkoutType.KAYAKING),
    ("stand_up_paddling", WorkoutType.STAND_UP_PADDLEBOARDING),
    ("surfing", WorkoutType.SURFING),
    ("sailing", WorkoutType.SAILING),
    ("water_polo", WorkoutType.WATER_POLO),
    # Strength & Gym
    ("strength_training", WorkoutType.STRENGTH_TRAINING),
    ("weightlifting", WorkoutType.STRENGTH_TRAINING),
    ("functional_training", WorkoutType.CARDIO_TRAINING),
    ("hiit", WorkoutType.CARDIO_TRAINING),
    ("circuit_training", WorkoutType.CARDIO_TRAINING),
    ("elliptical", WorkoutType.ELLIPTICAL),
    ("stair_climbing", WorkoutType.STAIR_CLIMBING),
    ("jump_rope", WorkoutType.CARDIO_TRAINING),
    # Flexibility & Mind-Body
    ("yoga", WorkoutType.YOGA),
    ("pilates", WorkoutType.PILATES),
    ("stretching", WorkoutType.STRETCHING),
    ("meditation", WorkoutType.MEDITATION),
    ("breathwork", WorkoutType.MEDITATION),
    # Winter Sports
    ("skiing", WorkoutType.ALPINE_SKIING),
    ("cross_country_skiing", WorkoutType.CROSS_COUNTRY_SKIING),
    ("snowboarding", WorkoutType.SNOWBOARDING),
    ("ice_skating", WorkoutType.ICE_SKATING),
    # Team Sports
    ("soccer", WorkoutType.SOCCER),
    ("basketball", WorkoutType.BASKETBALL),
    ("volleyball", WorkoutType.VOLLEYBALL),
    ("baseball", WorkoutType.BASEBALL),
    ("rugby", WorkoutType.RUGBY),
    ("cricket", WorkoutType.CRICKET),
    ("handball", WorkoutType.HANDBALL),
    ("lacrosse", WorkoutType.LACROSSE),
    ("american_football", WorkoutType.AMERICAN_FOOTBALL),
    ("ice_hockey", WorkoutType.HOCKEY),
    ("field_hockey", WorkoutType.HOCKEY),
    # Racket Sports
    ("tennis", WorkoutType.TENNIS),
    ("squash", WorkoutType.SQUASH),
    ("badminton", WorkoutType.BADMINTON),
    ("table_tennis", WorkoutType.TABLE_TENNIS),
    ("pickleball", WorkoutType.PICKLEBALL),
    ("padel", WorkoutType.PADEL),
    # Combat Sports
    ("boxing", WorkoutType.BOXING),
    ("martial_arts", WorkoutType.MARTIAL_ARTS),
    ("wrestling", WorkoutType.WRESTLING),
    # Climbing
    ("rock_climbing", WorkoutType.ROCK_CLIMBING),
    ("climbing", WorkoutType.ROCK_CLIMBING),
    # Golf
    ("golf", WorkoutType.GOLF),
    # Skating
    ("inline_skating", WorkoutType.INLINE_SKATING),
    ("skateboarding", WorkoutType.SKATEBOARDING),
    # Equestrian
    ("horseback_riding", WorkoutType.HORSEBACK_RIDING),
    # Dance & Group Fitness
    ("dancing", WorkoutType.DANCE),
    ("dance", WorkoutType.DANCE),
    ("group_exercise", WorkoutType.GROUP_EXERCISE),
    ("aerobics", WorkoutType.GROUP_EXERCISE),
    # Gymnastics
    ("gymnastics", WorkoutType.GYMNASTICS),
    # Multisport
    ("triathlon", WorkoutType.TRIATHLON),
    # Other / Generic
    ("other", WorkoutType.OTHER),
    ("activity", WorkoutType.OTHER),
    ("workout", WorkoutType.OTHER),
    ("rest", WorkoutType.OTHER),
    ("recovery", WorkoutType.OTHER),
]

# Create lookup dictionary (case-insensitive)
OURA_TO_UNIFIED: dict[str, WorkoutType] = {
    activity.lower(): unified_type for activity, unified_type in OURA_WORKOUT_TYPE_MAPPINGS
}


def get_unified_workout_type(oura_activity: str | None) -> WorkoutType:
    """Convert Oura activity string to unified WorkoutType.

    Args:
        oura_activity: Oura activity string (e.g. "running", "cycling")

    Returns:
        Unified WorkoutType enum value
    """
    if not oura_activity:
        return WorkoutType.OTHER

    normalized = oura_activity.lower().strip()
    return OURA_TO_UNIFIED.get(normalized, WorkoutType.OTHER)
