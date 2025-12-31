from app.schemas.workout_types import WorkoutType

# Whoop uses lowercase sport_name strings (e.g., "running", "cycling")
# Format: (whoop_sport_name, unified_type)
WHOOP_WORKOUT_TYPE_MAPPINGS: list[tuple[str, WorkoutType]] = [
    # Running & Walking
    ("running", WorkoutType.RUNNING),
    ("trail_running", WorkoutType.TRAIL_RUNNING),
    ("treadmill", WorkoutType.TREADMILL),
    ("walking", WorkoutType.WALKING),
    ("hiking", WorkoutType.HIKING),
    ("mountaineering", WorkoutType.MOUNTAINEERING),
    # Cycling
    ("cycling", WorkoutType.CYCLING),
    ("mountain_biking", WorkoutType.MOUNTAIN_BIKING),
    ("indoor_cycling", WorkoutType.INDOOR_CYCLING),
    ("cyclocross", WorkoutType.CYCLOCROSS),
    # Swimming
    ("swimming", WorkoutType.SWIMMING),
    ("pool_swimming", WorkoutType.POOL_SWIMMING),
    ("open_water_swimming", WorkoutType.OPEN_WATER_SWIMMING),
    # Strength & Gym
    ("strength_training", WorkoutType.STRENGTH_TRAINING),
    ("cardio_training", WorkoutType.CARDIO_TRAINING),
    ("fitness_equipment", WorkoutType.FITNESS_EQUIPMENT),
    ("elliptical", WorkoutType.ELLIPTICAL),
    ("rowing_machine", WorkoutType.ROWING_MACHINE),
    ("stair_climbing", WorkoutType.STAIR_CLIMBING),
    # Flexibility & Mind-Body
    ("yoga", WorkoutType.YOGA),
    ("pilates", WorkoutType.PILATES),
    ("stretching", WorkoutType.STRETCHING),
    # Winter Sports
    ("cross_country_skiing", WorkoutType.CROSS_COUNTRY_SKIING),
    ("alpine_skiing", WorkoutType.ALPINE_SKIING),
    ("backcountry_skiing", WorkoutType.BACKCOUNTRY_SKIING),
    ("downhill_skiing", WorkoutType.DOWNHILL_SKIING),
    ("snowboarding", WorkoutType.SNOWBOARDING),
    ("snowshoeing", WorkoutType.SNOWSHOEING),
    ("ice_skating", WorkoutType.ICE_SKATING),
    # Water Sports
    ("rowing", WorkoutType.ROWING),
    ("kayaking", WorkoutType.KAYAKING),
    ("canoeing", WorkoutType.CANOEING),
    ("paddling", WorkoutType.PADDLING),
    ("stand_up_paddleboarding", WorkoutType.STAND_UP_PADDLEBOARDING),
    ("surfing", WorkoutType.SURFING),
    ("kitesurfing", WorkoutType.KITESURFING),
    ("windsurfing", WorkoutType.WINDSURFING),
    ("sailing", WorkoutType.SAILING),
    # Team Sports
    ("soccer", WorkoutType.SOCCER),
    ("basketball", WorkoutType.BASKETBALL),
    ("football", WorkoutType.FOOTBALL),
    ("american_football", WorkoutType.AMERICAN_FOOTBALL),
    ("baseball", WorkoutType.BASEBALL),
    ("tennis", WorkoutType.TENNIS),
    ("badminton", WorkoutType.BADMINTON),
    ("volleyball", WorkoutType.VOLLEYBALL),
    ("handball", WorkoutType.HANDBALL),
    ("rugby", WorkoutType.RUGBY),
    ("hockey", WorkoutType.HOCKEY),
    ("floorball", WorkoutType.FLOORBALL),
    # Racket Sports
    ("squash", WorkoutType.SQUASH),
    ("table_tennis", WorkoutType.TABLE_TENNIS),
    ("padel", WorkoutType.PADEL),
    ("pickleball", WorkoutType.PICKLEBALL),
    # Combat Sports
    ("boxing", WorkoutType.BOXING),
    ("martial_arts", WorkoutType.MARTIAL_ARTS),
    # Outdoor Activities
    ("rock_climbing", WorkoutType.ROCK_CLIMBING),
    ("indoor_climbing", WorkoutType.INDOOR_CLIMBING),
    ("bouldering", WorkoutType.BOULDERING),
    ("trail_hiking", WorkoutType.TRAIL_HIKING),
    ("orienteering", WorkoutType.ORIENTEERING),
    # Other Sports
    ("golf", WorkoutType.GOLF),
    ("skating", WorkoutType.SKATING),
    ("inline_skating", WorkoutType.INLINE_SKATING),
    ("skateboarding", WorkoutType.SKATEBOARDING),
    ("horseback_riding", WorkoutType.HORSEBACK_RIDING),
    # Multisport
    ("triathlon", WorkoutType.TRIATHLON),
    ("multisport", WorkoutType.MULTISPORT),
    # Motor Sports
    ("motorcycling", WorkoutType.MOTORCYCLING),
    ("motor_sports", WorkoutType.MOTOR_SPORTS),
    # Dance & Group Fitness
    ("dance", WorkoutType.DANCE),
    ("aerobics", WorkoutType.AEROBICS),
    ("group_exercise", WorkoutType.GROUP_EXERCISE),
    # E-Sports & Alternative
    ("e_biking", WorkoutType.E_BIKING),
    ("virtual_activity", WorkoutType.VIRTUAL_ACTIVITY),
    # Diving
    ("diving", WorkoutType.DIVING),
    ("snorkeling", WorkoutType.SNORKELING),
    # Casual & General
    ("walking_fitness", WorkoutType.WALKING_FITNESS),
    ("casual_walking", WorkoutType.CASUAL_WALKING),
    # Transition
    ("transition", WorkoutType.TRANSITION),
    # Generic/Other
    ("generic", WorkoutType.GENERIC),
    ("other", WorkoutType.OTHER),
    ("sport", WorkoutType.SPORT),
]

# Create lookup dictionary (case-insensitive)
WHOOP_TO_UNIFIED: dict[str, WorkoutType] = {
    sport_name.lower(): unified_type for sport_name, unified_type in WHOOP_WORKOUT_TYPE_MAPPINGS
}


def get_unified_workout_type(whoop_sport_name: str | None, whoop_sport_id: int | None = None) -> WorkoutType:
    """
    Convert Whoop sport name to unified WorkoutType.

    Args:
        whoop_sport_name: Whoop sport name string (e.g., "running", "cycling")
        whoop_sport_id: Whoop sport ID (optional fallback, not currently used)

    Returns:
        Unified WorkoutType enum value

    Examples:
        >>> get_unified_workout_type("running")
        WorkoutType.RUNNING
        >>> get_unified_workout_type("cycling")
        WorkoutType.CYCLING
        >>> get_unified_workout_type("yoga")
        WorkoutType.YOGA
        >>> get_unified_workout_type("unknown_sport")
        WorkoutType.OTHER
        >>> get_unified_workout_type(None)
        WorkoutType.OTHER

    Note:
        - Whoop uses lowercase strings for sport names
        - If sport_name is missing, defaults to WorkoutType.OTHER
        - sport_id is included for potential future use but not currently mapped
    """
    if not whoop_sport_name:
        return WorkoutType.OTHER

    normalized = whoop_sport_name.lower().strip()
    return WHOOP_TO_UNIFIED.get(normalized, WorkoutType.OTHER)

