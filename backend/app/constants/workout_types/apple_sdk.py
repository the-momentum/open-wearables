from app.schemas.workout_types import WorkoutType

# HealthKit HKWorkoutActivityType mappings
# Source: Apple HealthKit Framework Documentation
# Format: (healthkit_activity_type, unified_type)
SDK_WORKOUT_TYPE_MAPPINGS: list[tuple[str, WorkoutType]] = [
    # Exercise and Fitness
    ("walking", WorkoutType.WALKING),
    ("running", WorkoutType.RUNNING),
    ("cycling", WorkoutType.CYCLING),
    ("wheelchair_walk", WorkoutType.WALKING),
    ("wheelchair_run", WorkoutType.RUNNING),
    ("hand_cycling", WorkoutType.CYCLING),
    ("elliptical", WorkoutType.ELLIPTICAL),
    ("stair_climbing", WorkoutType.STAIR_CLIMBING),
    ("stairs", WorkoutType.STAIR_CLIMBING),
    ("jump_rope", WorkoutType.CARDIO_TRAINING),
    ("core_training", WorkoutType.STRENGTH_TRAINING),
    ("functional_strength_training", WorkoutType.STRENGTH_TRAINING),
    ("strength_training", WorkoutType.STRENGTH_TRAINING),
    ("cross_training", WorkoutType.CARDIO_TRAINING),
    ("mixed_cardio", WorkoutType.CARDIO_TRAINING),
    ("hiit", WorkoutType.CARDIO_TRAINING),
    ("step_training", WorkoutType.AEROBICS),
    ("fitness_gaming", WorkoutType.OTHER),
    ("preparation_and_recovery", WorkoutType.STRETCHING),
    ("flexibility", WorkoutType.STRETCHING),
    ("cooldown", WorkoutType.STRETCHING),
    # Studio Activities
    ("barre", WorkoutType.AEROBICS),
    ("cardio_dance", WorkoutType.DANCE),
    ("social_dance", WorkoutType.DANCE),
    ("yoga", WorkoutType.YOGA),
    ("mind_and_body", WorkoutType.STRETCHING),
    ("pilates", WorkoutType.PILATES),
    # Team Sports
    ("american_football", WorkoutType.AMERICAN_FOOTBALL),
    ("australian_football", WorkoutType.FOOTBALL),
    ("baseball", WorkoutType.BASEBALL),
    ("basketball", WorkoutType.BASKETBALL),
    ("cricket", WorkoutType.OTHER),
    ("disc_sports", WorkoutType.OTHER),
    ("handball", WorkoutType.HANDBALL),
    ("hockey", WorkoutType.HOCKEY),
    ("lacrosse", WorkoutType.OTHER),
    ("rugby", WorkoutType.RUGBY),
    ("soccer", WorkoutType.SOCCER),
    ("softball", WorkoutType.BASEBALL),
    ("volleyball", WorkoutType.VOLLEYBALL),
    # Racket Sports
    ("badminton", WorkoutType.BADMINTON),
    ("pickleball", WorkoutType.PICKLEBALL),
    ("racquetball", WorkoutType.OTHER),
    ("squash", WorkoutType.SQUASH),
    ("table_tennis", WorkoutType.TABLE_TENNIS),
    ("tennis", WorkoutType.TENNIS),
    # Outdoor Activities
    ("climbing", WorkoutType.ROCK_CLIMBING),
    ("equestrian", WorkoutType.HORSEBACK_RIDING),
    ("fishing", WorkoutType.OTHER),
    ("golf", WorkoutType.GOLF),
    ("hiking", WorkoutType.HIKING),
    ("hunting", WorkoutType.OTHER),
    ("play", WorkoutType.OTHER),
    # Snow and Ice Sports
    ("cross_country_skiing", WorkoutType.CROSS_COUNTRY_SKIING),
    ("curling", WorkoutType.OTHER),
    ("downhill_skiing", WorkoutType.ALPINE_SKIING),
    ("snow_sports", WorkoutType.OTHER),
    ("snowboarding", WorkoutType.SNOWBOARDING),
    ("skating", WorkoutType.ICE_SKATING),
    # Water Activities
    ("paddle_sports", WorkoutType.PADDLING),
    ("rowing", WorkoutType.ROWING),
    ("sailing", WorkoutType.SAILING),
    ("surfing", WorkoutType.SURFING),
    ("swimming", WorkoutType.SWIMMING),
    ("underwater_diving", WorkoutType.DIVING),
    ("water_fitness", WorkoutType.SWIMMING),
    ("water_polo", WorkoutType.OTHER),
    ("water_sports", WorkoutType.OTHER),
    # Martial Arts
    ("boxing", WorkoutType.BOXING),
    ("kickboxing", WorkoutType.BOXING),
    ("martial_arts", WorkoutType.MARTIAL_ARTS),
    ("tai_chi", WorkoutType.MARTIAL_ARTS),
    ("wrestling", WorkoutType.MARTIAL_ARTS),
    # Individual Sports
    ("archery", WorkoutType.OTHER),
    ("bowling", WorkoutType.OTHER),
    ("fencing", WorkoutType.OTHER),
    ("gymnastics", WorkoutType.FITNESS_EQUIPMENT),
    ("track_and_field", WorkoutType.RUNNING),
    # Multisport Activities
    ("swim_bike_run", WorkoutType.TRIATHLON),
    ("transition", WorkoutType.TRANSITION),
    # Deprecated (but still supported for backward compatibility)
    ("dance", WorkoutType.DANCE),
    ("dance_inspired_training", WorkoutType.DANCE),
    ("mixed_metabolic_cardio_training", WorkoutType.CARDIO_TRAINING),
    # Other
    ("other", WorkoutType.OTHER),
]


SDK_TO_UNIFIED: dict[str, WorkoutType] = {
    activity_type: unified_type for activity_type, unified_type in SDK_WORKOUT_TYPE_MAPPINGS
}


def get_unified_workout_type(sdk_activity_type: str) -> WorkoutType:
    """
    Convert SDK activity type to unified WorkoutType.

    Args:
        sdk_activity_type: SDK activity type string in snake_case
                                (e.g., "running", "cycling", "yoga")

    Returns:
        Unified WorkoutType enum value

    Examples:
        >>> get_unified_workout_type("running")
        WorkoutType.RUNNING
        >>> get_unified_workout_type("cycling")
        WorkoutType.CYCLING
        >>> get_unified_workout_type("yoga")
        WorkoutType.YOGA
        >>> get_unified_workout_type("other")
        WorkoutType.OTHER
    Note:
        Some deprecated types are still supported for backward compatibility:
        - dance
        - dance_inspired_training
        - mixed_metabolic_cardio_training
    """
    return SDK_TO_UNIFIED.get(sdk_activity_type, WorkoutType.OTHER)


def get_activity_name(sdk_activity_type: str) -> str:
    """
    Convert snake_case activity type to human-readable name.
    Examples:
        >>> get_activity_name("running")
        "Running"
        >>> get_activity_name("hiit")
        "Hiit"
        >>> get_activity_name("cross_country_skiing")
        "Cross Country Skiing"
    """
    return sdk_activity_type.replace("_", " ").title()
