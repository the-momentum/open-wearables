from app.schemas.workout_types import WorkoutType

# WHOOP workout type mappings based on WHOOP API documentation
# Reference: https://developer.whoop.com/docs/developing/user-data/workout
# WHOOP uses lowercase sport_name strings (e.g., "running", "cycling")
# Format: (whoop_sport_name, unified_type)
WHOOP_WORKOUT_TYPE_MAPPINGS: list[tuple[str, WorkoutType]] = [
    # Running & Walking
    ("running", WorkoutType.RUNNING),
    ("walking", WorkoutType.WALKING),
    ("hiking/rucking", WorkoutType.HIKING),
    ("track & field", WorkoutType.RUNNING),
    ("stroller walking", WorkoutType.WALKING),
    ("stroller jogging", WorkoutType.RUNNING),
    ("dog walking", WorkoutType.WALKING),
    ("caddying", WorkoutType.WALKING),
    ("toddlerwearing", WorkoutType.WALKING),
    ("babywearing", WorkoutType.WALKING),
    # Cycling
    ("cycling", WorkoutType.CYCLING),
    ("mountain biking", WorkoutType.MOUNTAIN_BIKING),
    ("spin", WorkoutType.INDOOR_CYCLING),
    ("assault bike", WorkoutType.INDOOR_CYCLING),
    # Swimming & Water Sports
    ("swimming", WorkoutType.SWIMMING),
    ("water polo", WorkoutType.WATER_POLO),
    ("rowing", WorkoutType.ROWING),
    ("kayaking", WorkoutType.KAYAKING),
    ("paddleboarding", WorkoutType.STAND_UP_PADDLEBOARDING),
    ("surfing", WorkoutType.SURFING),
    ("sailing", WorkoutType.SAILING),
    ("diving", WorkoutType.DIVING),
    ("water skiing", WorkoutType.SURFING),
    ("wakeboarding", WorkoutType.SURFING),
    ("kite boarding", WorkoutType.KITESURFING),
    ("operations - water", WorkoutType.OTHER),
    # Strength & Gym
    ("weightlifting", WorkoutType.STRENGTH_TRAINING),
    ("powerlifting", WorkoutType.STRENGTH_TRAINING),
    ("strength trainer", WorkoutType.STRENGTH_TRAINING),
    ("functional fitness", WorkoutType.CARDIO_TRAINING),
    ("elliptical", WorkoutType.ELLIPTICAL),
    ("stairmaster", WorkoutType.STAIR_CLIMBING),
    ("climber", WorkoutType.STAIR_CLIMBING),
    ("stadium steps", WorkoutType.STAIR_CLIMBING),
    ("hiit", WorkoutType.CARDIO_TRAINING),
    ("jumping rope", WorkoutType.CARDIO_TRAINING),
    ("obstacle course racing", WorkoutType.CARDIO_TRAINING),
    ("parkour", WorkoutType.CARDIO_TRAINING),
    # Flexibility & Mind-Body
    ("yoga", WorkoutType.YOGA),
    ("hot yoga", WorkoutType.YOGA),
    ("pilates", WorkoutType.PILATES),
    ("stretching", WorkoutType.STRETCHING),
    ("meditation", WorkoutType.MEDITATION),
    ("barre", WorkoutType.GROUP_EXERCISE),
    ("barre3", WorkoutType.GROUP_EXERCISE),
    # Winter Sports
    ("skiing", WorkoutType.ALPINE_SKIING),
    ("cross country skiing", WorkoutType.CROSS_COUNTRY_SKIING),
    ("snowboarding", WorkoutType.SNOWBOARDING),
    ("ice skating", WorkoutType.ICE_SKATING),
    # Team Sports - Ball Sports
    ("soccer", WorkoutType.SOCCER),
    ("basketball", WorkoutType.BASKETBALL),
    ("football", WorkoutType.AMERICAN_FOOTBALL),
    ("australian football", WorkoutType.FOOTBALL),
    ("gaelic football", WorkoutType.FOOTBALL),
    ("baseball", WorkoutType.BASEBALL),
    ("softball", WorkoutType.BASEBALL),
    ("volleyball", WorkoutType.VOLLEYBALL),
    ("rugby", WorkoutType.RUGBY),
    ("lacrosse", WorkoutType.LACROSSE),
    ("cricket", WorkoutType.CRICKET),
    ("netball", WorkoutType.SPORT),
    ("ultimate", WorkoutType.SPORT),
    ("spikeball", WorkoutType.SPORT),
    ("hurling/camogie", WorkoutType.SPORT),
    # Team Sports - Hockey
    ("ice hockey", WorkoutType.HOCKEY),
    ("field hockey", WorkoutType.HOCKEY),
    # Racket Sports
    ("tennis", WorkoutType.TENNIS),
    ("squash", WorkoutType.SQUASH),
    ("badminton", WorkoutType.BADMINTON),
    ("table tennis", WorkoutType.TABLE_TENNIS),
    ("padel", WorkoutType.PADEL),
    ("pickleball", WorkoutType.PICKLEBALL),
    ("paddle tennis", WorkoutType.PADEL),
    # Combat Sports
    ("boxing", WorkoutType.BOXING),
    ("kickboxing", WorkoutType.BOXING),
    ("box fitness", WorkoutType.BOXING),
    ("martial arts", WorkoutType.MARTIAL_ARTS),
    ("jiu jitsu", WorkoutType.MARTIAL_ARTS),
    ("wrestling", WorkoutType.WRESTLING),
    ("fencing", WorkoutType.MARTIAL_ARTS),
    # Climbing
    ("rock climbing", WorkoutType.ROCK_CLIMBING),
    # Golf
    ("golf", WorkoutType.GOLF),
    ("disc golf", WorkoutType.GOLF),
    # Skating
    ("inline skating", WorkoutType.INLINE_SKATING),
    ("skateboarding", WorkoutType.SKATEBOARDING),
    # Equestrian
    ("horseback riding", WorkoutType.HORSEBACK_RIDING),
    ("polo", WorkoutType.HORSEBACK_RIDING),
    # Multisport
    ("triathlon", WorkoutType.TRIATHLON),
    ("duathlon", WorkoutType.MULTISPORT),
    # Motor Sports
    ("motocross", WorkoutType.MOTORCYCLING),
    ("motor racing", WorkoutType.MOTOR_SPORTS),
    # Dance & Group Fitness
    ("dance", WorkoutType.DANCE),
    ("circus arts", WorkoutType.DANCE),
    ("stage performance", WorkoutType.DANCE),
    ("f45 training", WorkoutType.GROUP_EXERCISE),
    ("barry's", WorkoutType.GROUP_EXERCISE),
    # Gymnastics
    ("gymnastics", WorkoutType.GYMNASTICS),
    # Handball
    ("handball", WorkoutType.HANDBALL),
    # Recovery & Wellness (map to OTHER as not traditional workouts)
    ("ice bath", WorkoutType.OTHER),
    ("sauna", WorkoutType.OTHER),
    ("massage therapy", WorkoutType.OTHER),
    ("air compression", WorkoutType.OTHER),
    ("percussive massage", WorkoutType.OTHER),
    # Work & Daily Activities (map to OTHER)
    ("operations - tactical", WorkoutType.OTHER),
    ("operations - medical", WorkoutType.OTHER),
    ("operations - flying", WorkoutType.OTHER),
    ("manual labor", WorkoutType.OTHER),
    ("high stress work", WorkoutType.OTHER),
    ("coaching", WorkoutType.OTHER),
    ("watching sports", WorkoutType.OTHER),
    ("commuting", WorkoutType.OTHER),
    ("gaming", WorkoutType.OTHER),
    ("yard work", WorkoutType.OTHER),
    ("cooking", WorkoutType.OTHER),
    ("cleaning", WorkoutType.OTHER),
    ("public speaking", WorkoutType.OTHER),
    ("musical performance", WorkoutType.OTHER),
    ("dedicated parenting", WorkoutType.OTHER),
    ("wheelchair pushing", WorkoutType.WALKING),
    # Outdoor Activities
    ("paintball", WorkoutType.SPORT),
    # Generic/Other
    ("activity", WorkoutType.OTHER),
    ("other", WorkoutType.OTHER),
]

# Create lookup dictionary (case-insensitive)
WHOOP_TO_UNIFIED: dict[str, WorkoutType] = {
    sport_name.lower(): unified_type for sport_name, unified_type in WHOOP_WORKOUT_TYPE_MAPPINGS
}


def get_unified_workout_type(whoop_sport_name: str | None) -> WorkoutType:
    """
    Convert Whoop sport name to unified WorkoutType.

    Args:
        whoop_sport_name: Whoop sport name string (e.g., "running", "cycling")

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
    """
    if not whoop_sport_name:
        return WorkoutType.OTHER

    normalized = whoop_sport_name.lower().strip()
    return WHOOP_TO_UNIFIED.get(normalized, WorkoutType.OTHER)
