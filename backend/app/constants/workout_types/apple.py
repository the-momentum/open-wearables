import re

from app.schemas.workout_types import WorkoutType

# HealthKit HKWorkoutActivityType mappings
# Source: Apple HealthKit Framework Documentation
# Format: (healthkit_activity_type, unified_type)
HEALTHKIT_WORKOUT_TYPE_MAPPINGS: list[tuple[str, WorkoutType]] = [
    # Exercise and Fitness
    ("HKWorkoutActivityTypeWalking", WorkoutType.WALKING),
    ("HKWorkoutActivityTypeRunning", WorkoutType.RUNNING),
    ("HKWorkoutActivityTypeCycling", WorkoutType.CYCLING),
    ("HKWorkoutActivityTypeWheelchairWalkPace", WorkoutType.WALKING),
    ("HKWorkoutActivityTypeWheelchairRunPace", WorkoutType.RUNNING),
    ("HKWorkoutActivityTypeHandCycling", WorkoutType.CYCLING),
    ("HKWorkoutActivityTypeElliptical", WorkoutType.ELLIPTICAL),
    ("HKWorkoutActivityTypeStairClimbing", WorkoutType.STAIR_CLIMBING),
    ("HKWorkoutActivityTypeStairs", WorkoutType.STAIR_CLIMBING),
    ("HKWorkoutActivityTypeJumpRope", WorkoutType.CARDIO_TRAINING),
    ("HKWorkoutActivityTypeCoreTraining", WorkoutType.STRENGTH_TRAINING),
    ("HKWorkoutActivityTypeFunctionalStrengthTraining", WorkoutType.STRENGTH_TRAINING),
    ("HKWorkoutActivityTypeTraditionalStrengthTraining", WorkoutType.STRENGTH_TRAINING),
    ("HKWorkoutActivityTypeCrossTraining", WorkoutType.CARDIO_TRAINING),
    ("HKWorkoutActivityTypeMixedCardio", WorkoutType.CARDIO_TRAINING),
    ("HKWorkoutActivityTypeHighIntensityIntervalTraining", WorkoutType.CARDIO_TRAINING),
    ("HKWorkoutActivityTypeStepTraining", WorkoutType.AEROBICS),
    ("HKWorkoutActivityTypeFitnessGaming", WorkoutType.OTHER),
    ("HKWorkoutActivityTypePreparationAndRecovery", WorkoutType.STRETCHING),
    ("HKWorkoutActivityTypeFlexibility", WorkoutType.STRETCHING),
    ("HKWorkoutActivityTypeCooldown", WorkoutType.STRETCHING),
    # Studio Activities
    ("HKWorkoutActivityTypeBarre", WorkoutType.AEROBICS),
    ("HKWorkoutActivityTypeCardioDance", WorkoutType.DANCE),
    ("HKWorkoutActivityTypeSocialDance", WorkoutType.DANCE),
    ("HKWorkoutActivityTypeYoga", WorkoutType.YOGA),
    ("HKWorkoutActivityTypeMindAndBody", WorkoutType.STRETCHING),
    ("HKWorkoutActivityTypePilates", WorkoutType.PILATES),
    # Team Sports
    ("HKWorkoutActivityTypeAmericanFootball", WorkoutType.AMERICAN_FOOTBALL),
    ("HKWorkoutActivityTypeAustralianFootball", WorkoutType.FOOTBALL),
    ("HKWorkoutActivityTypeBaseball", WorkoutType.BASEBALL),
    ("HKWorkoutActivityTypeBasketball", WorkoutType.BASKETBALL),
    ("HKWorkoutActivityTypeCricket", WorkoutType.OTHER),
    ("HKWorkoutActivityTypeDiscSports", WorkoutType.OTHER),
    ("HKWorkoutActivityTypeHandball", WorkoutType.HANDBALL),
    ("HKWorkoutActivityTypeHockey", WorkoutType.HOCKEY),
    ("HKWorkoutActivityTypeLacrosse", WorkoutType.OTHER),
    ("HKWorkoutActivityTypeRugby", WorkoutType.RUGBY),
    ("HKWorkoutActivityTypeSoccer", WorkoutType.SOCCER),
    ("HKWorkoutActivityTypeSoftball", WorkoutType.BASEBALL),
    ("HKWorkoutActivityTypeVolleyball", WorkoutType.VOLLEYBALL),
    # Racket Sports
    ("HKWorkoutActivityTypeBadminton", WorkoutType.BADMINTON),
    ("HKWorkoutActivityTypePickleball", WorkoutType.OTHER),
    ("HKWorkoutActivityTypeRacquetball", WorkoutType.OTHER),
    ("HKWorkoutActivityTypeSquash", WorkoutType.SQUASH),
    ("HKWorkoutActivityTypeTableTennis", WorkoutType.TABLE_TENNIS),
    ("HKWorkoutActivityTypeTennis", WorkoutType.TENNIS),
    # Outdoor Activities
    ("HKWorkoutActivityTypeClimbing", WorkoutType.ROCK_CLIMBING),
    ("HKWorkoutActivityTypeEquestrianSports", WorkoutType.HORSEBACK_RIDING),
    ("HKWorkoutActivityTypeFishing", WorkoutType.OTHER),
    ("HKWorkoutActivityTypeGolf", WorkoutType.GOLF),
    ("HKWorkoutActivityTypeHiking", WorkoutType.HIKING),
    ("HKWorkoutActivityTypeHunting", WorkoutType.OTHER),
    ("HKWorkoutActivityTypePlay", WorkoutType.OTHER),
    # Snow and Ice Sports
    ("HKWorkoutActivityTypeCrossCountrySkiing", WorkoutType.CROSS_COUNTRY_SKIING),
    ("HKWorkoutActivityTypeCurling", WorkoutType.OTHER),
    ("HKWorkoutActivityTypeDownhillSkiing", WorkoutType.ALPINE_SKIING),
    ("HKWorkoutActivityTypeSnowSports", WorkoutType.OTHER),
    ("HKWorkoutActivityTypeSnowboarding", WorkoutType.SNOWBOARDING),
    ("HKWorkoutActivityTypeSkatingSports", WorkoutType.ICE_SKATING),
    # Water Activities
    ("HKWorkoutActivityTypePaddleSports", WorkoutType.PADDLING),
    ("HKWorkoutActivityTypeRowing", WorkoutType.ROWING),
    ("HKWorkoutActivityTypeSailing", WorkoutType.SAILING),
    ("HKWorkoutActivityTypeSurfingSports", WorkoutType.SURFING),
    ("HKWorkoutActivityTypeSwimming", WorkoutType.SWIMMING),
    ("HKWorkoutActivityTypeUnderwaterDiving", WorkoutType.DIVING),
    ("HKWorkoutActivityTypeWaterFitness", WorkoutType.SWIMMING),
    ("HKWorkoutActivityTypeWaterPolo", WorkoutType.OTHER),
    ("HKWorkoutActivityTypeWaterSports", WorkoutType.OTHER),
    # Martial Arts
    ("HKWorkoutActivityTypeBoxing", WorkoutType.BOXING),
    ("HKWorkoutActivityTypeKickboxing", WorkoutType.BOXING),
    ("HKWorkoutActivityTypeMartialArts", WorkoutType.MARTIAL_ARTS),
    ("HKWorkoutActivityTypeTaiChi", WorkoutType.MARTIAL_ARTS),
    ("HKWorkoutActivityTypeWrestling", WorkoutType.MARTIAL_ARTS),
    # Individual Sports
    ("HKWorkoutActivityTypeArchery", WorkoutType.OTHER),
    ("HKWorkoutActivityTypeBowling", WorkoutType.OTHER),
    ("HKWorkoutActivityTypeFencing", WorkoutType.OTHER),
    ("HKWorkoutActivityTypeGymnastics", WorkoutType.FITNESS_EQUIPMENT),
    ("HKWorkoutActivityTypeTrackAndField", WorkoutType.RUNNING),
    # Multisport Activities
    ("HKWorkoutActivityTypeSwimBikeRun", WorkoutType.TRIATHLON),
    ("HKWorkoutActivityTypeTransition", WorkoutType.TRANSITION),
    # Deprecated (but still supported for backward compatibility)
    ("HKWorkoutActivityTypeDance", WorkoutType.DANCE),
    ("HKWorkoutActivityTypeDanceInspiredTraining", WorkoutType.DANCE),
    ("HKWorkoutActivityTypeMixedMetabolicCardioTraining", WorkoutType.CARDIO_TRAINING),
    # Other
    ("HKWorkoutActivityTypeOther", WorkoutType.OTHER),
]


HEALTHKIT_TO_UNIFIED: dict[str, WorkoutType] = {
    activity_type: unified_type for activity_type, unified_type in HEALTHKIT_WORKOUT_TYPE_MAPPINGS
}


def get_unified_workout_type(healthkit_activity_type: str) -> WorkoutType:
    """
    Convert HealthKit HKWorkoutActivityType to unified WorkoutType.

    Args:
        healthkit_activity_type: HealthKit activity type string
                                (e.g., "HKWorkoutActivityTypeRunning")

    Returns:
        Unified WorkoutType enum value

    Examples:
        >>> get_unified_workout_type("HKWorkoutActivityTypeRunning")
        WorkoutType.RUNNING
        >>> get_unified_workout_type("HKWorkoutActivityTypeCycling")
        WorkoutType.CYCLING
        >>> get_unified_workout_type("HKWorkoutActivityTypeYoga")
        WorkoutType.YOGA
        >>> get_unified_workout_type("HKWorkoutActivityTypeOther")
        WorkoutType.OTHER

    Note:
        Some deprecated types are still supported for backward compatibility:
        - HKWorkoutActivityTypeDance
        - HKWorkoutActivityTypeDanceInspiredTraining
        - HKWorkoutActivityTypeMixedMetabolicCardioTraining
    """
    return HEALTHKIT_TO_UNIFIED.get(healthkit_activity_type, WorkoutType.OTHER)


def get_healthkit_activity_name(healthkit_activity_type: str) -> str:
    """
    Extract human-readable name from HealthKit activity type.

    Examples:
        >>> get_healthkit_activity_name("HKWorkoutActivityTypeRunning")
        "Running"
        >>> get_healthkit_activity_name("HKWorkoutActivityTypeHighIntensityIntervalTraining")
        "High Intensity Interval Training"
    """
    # Remove prefix
    if healthkit_activity_type.startswith("HKWorkoutActivityType"):
        name = healthkit_activity_type[len("HKWorkoutActivityType") :]
        return re.sub(r"([A-Z])", r" \1", name).strip()
    return healthkit_activity_type
