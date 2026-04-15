from enum import StrEnum

from app.schemas.enums import WorkoutType


class SDKWorkoutType(StrEnum):
    """Apple HealthKit SDK workout activity types.

    These are the workout types sent from the iOS SDK in snake_case format.
    """

    # Exercise and Fitness
    WALKING = "walking"
    RUNNING = "running"
    CYCLING = "cycling"
    WHEELCHAIR_WALK = "wheelchair_walk"
    WHEELCHAIR_RUN = "wheelchair_run"
    HAND_CYCLING = "hand_cycling"
    ELLIPTICAL = "elliptical"
    STAIR_CLIMBING = "stair_climbing"
    STAIRS = "stairs"
    JUMP_ROPE = "jump_rope"
    CORE_TRAINING = "core_training"
    FUNCTIONAL_STRENGTH_TRAINING = "functional_strength_training"
    STRENGTH_TRAINING = "strength_training"
    CROSS_TRAINING = "cross_training"
    MIXED_CARDIO = "mixed_cardio"
    HIIT = "hiit"
    STEP_TRAINING = "step_training"
    FITNESS_GAMING = "fitness_gaming"
    PREPARATION_AND_RECOVERY = "preparation_and_recovery"
    FLEXIBILITY = "flexibility"
    COOLDOWN = "cooldown"

    # Studio Activities
    BARRE = "barre"
    CARDIO_DANCE = "cardio_dance"
    SOCIAL_DANCE = "social_dance"
    YOGA = "yoga"
    MIND_AND_BODY = "mind_and_body"
    PILATES = "pilates"

    # Team Sports
    AMERICAN_FOOTBALL = "american_football"
    AUSTRALIAN_FOOTBALL = "australian_football"
    BASEBALL = "baseball"
    BASKETBALL = "basketball"
    CRICKET = "cricket"
    DISC_SPORTS = "disc_sports"
    HANDBALL = "handball"
    HOCKEY = "hockey"
    LACROSSE = "lacrosse"
    RUGBY = "rugby"
    SOCCER = "soccer"
    SOFTBALL = "softball"
    VOLLEYBALL = "volleyball"

    # Racket Sports
    BADMINTON = "badminton"
    PICKLEBALL = "pickleball"
    RACQUETBALL = "racquetball"
    SQUASH = "squash"
    TABLE_TENNIS = "table_tennis"
    TENNIS = "tennis"

    # Outdoor Activities
    CLIMBING = "climbing"
    EQUESTRIAN = "equestrian"
    FISHING = "fishing"
    GOLF = "golf"
    HIKING = "hiking"
    HUNTING = "hunting"
    PLAY = "play"

    # Snow and Ice Sports
    CROSS_COUNTRY_SKIING = "cross_country_skiing"
    CURLING = "curling"
    DOWNHILL_SKIING = "downhill_skiing"
    SNOW_SPORTS = "snow_sports"
    SNOWBOARDING = "snowboarding"
    SKATING = "skating"

    # Water Activities
    PADDLE_SPORTS = "paddle_sports"
    ROWING = "rowing"
    SAILING = "sailing"
    SURFING = "surfing"
    SWIMMING = "swimming"
    UNDERWATER_DIVING = "underwater_diving"
    WATER_FITNESS = "water_fitness"
    WATER_POLO = "water_polo"
    WATER_SPORTS = "water_sports"

    # Martial Arts
    BOXING = "boxing"
    KICKBOXING = "kickboxing"
    MARTIAL_ARTS = "martial_arts"
    TAI_CHI = "tai_chi"
    WRESTLING = "wrestling"

    # Individual Sports
    ARCHERY = "archery"
    BOWLING = "bowling"
    FENCING = "fencing"
    GYMNASTICS = "gymnastics"
    TRACK_AND_FIELD = "track_and_field"

    # Multisport Activities
    SWIM_BIKE_RUN = "swim_bike_run"
    TRANSITION = "transition"

    # Deprecated (but still supported for backward compatibility)
    DANCE = "dance"
    DANCE_INSPIRED_TRAINING = "dance_inspired_training"
    MIXED_METABOLIC_CARDIO_TRAINING = "mixed_metabolic_cardio_training"

    # Health Connect (Android) exercise vocabulary — written by third-party
    # writers like Peloton, Strava, and Zwift via the Health Connect SDK.
    # These names mirror the strings emitted by the Open Wearables Android
    # SDK's ``HealthConnectManager.mapExerciseType`` (see that file in the
    # ``open_wearables_android_sdk`` repo). The wire format is uppercase,
    # and ``get_unified_workout_type`` lowercases input before lookup so the
    # snake_case keys below match. Entries whose wire name already overlaps
    # an Apple HealthKit enum member (``BADMINTON``, ``CYCLING``, ``HIIT``,
    # ``RUNNING``, ``OTHER`` …) are reused above and not repeated here.
    CYCLING_STATIONARY = "cycling_stationary"
    BOOT_CAMP = "boot_camp"
    CALISTHENICS = "calisthenics"
    DANCING = "dancing"
    EXERCISE_CLASS = "exercise_class"
    FOOTBALL_AMERICAN = "football_american"
    FOOTBALL_AUSTRALIAN = "football_australian"
    FRISBEE_DISC = "frisbee_disc"
    GUIDED_BREATHING = "guided_breathing"
    ICE_HOCKEY = "ice_hockey"
    ICE_SKATING = "ice_skating"
    PADDLING = "paddling"
    PARAGLIDING = "paragliding"
    ROCK_CLIMBING = "rock_climbing"
    ROLLER_HOCKEY = "roller_hockey"
    ROWING_MACHINE = "rowing_machine"
    RUNNING_TREADMILL = "running_treadmill"
    SCUBA_DIVING = "scuba_diving"
    SKIING = "skiing"
    SNOWSHOEING = "snowshoeing"
    STAIR_CLIMBING_MACHINE = "stair_climbing_machine"
    STRETCHING = "stretching"
    SWIMMING_OPEN_WATER = "swimming_open_water"
    SWIMMING_POOL = "swimming_pool"
    WEIGHTLIFTING = "weightlifting"
    WHEELCHAIR = "wheelchair"

    # Other
    OTHER = "other"


# HealthKit HKWorkoutActivityType mappings
# Source: Apple HealthKit Framework Documentation
# Format: (healthkit_activity_type, unified_type)
SDK_WORKOUT_TYPE_MAPPINGS: list[tuple[SDKWorkoutType, WorkoutType]] = [
    # Exercise and Fitness
    (SDKWorkoutType.WALKING, WorkoutType.WALKING),
    (SDKWorkoutType.RUNNING, WorkoutType.RUNNING),
    (SDKWorkoutType.CYCLING, WorkoutType.CYCLING),
    (SDKWorkoutType.WHEELCHAIR_WALK, WorkoutType.WALKING),
    (SDKWorkoutType.WHEELCHAIR_RUN, WorkoutType.RUNNING),
    (SDKWorkoutType.HAND_CYCLING, WorkoutType.CYCLING),
    (SDKWorkoutType.ELLIPTICAL, WorkoutType.ELLIPTICAL),
    (SDKWorkoutType.STAIR_CLIMBING, WorkoutType.STAIR_CLIMBING),
    (SDKWorkoutType.STAIRS, WorkoutType.STAIR_CLIMBING),
    (SDKWorkoutType.JUMP_ROPE, WorkoutType.CARDIO_TRAINING),
    (SDKWorkoutType.CORE_TRAINING, WorkoutType.STRENGTH_TRAINING),
    (SDKWorkoutType.FUNCTIONAL_STRENGTH_TRAINING, WorkoutType.STRENGTH_TRAINING),
    (SDKWorkoutType.STRENGTH_TRAINING, WorkoutType.STRENGTH_TRAINING),
    (SDKWorkoutType.CROSS_TRAINING, WorkoutType.CARDIO_TRAINING),
    (SDKWorkoutType.MIXED_CARDIO, WorkoutType.CARDIO_TRAINING),
    (SDKWorkoutType.HIIT, WorkoutType.CARDIO_TRAINING),
    (SDKWorkoutType.STEP_TRAINING, WorkoutType.AEROBICS),
    (SDKWorkoutType.FITNESS_GAMING, WorkoutType.OTHER),
    (SDKWorkoutType.PREPARATION_AND_RECOVERY, WorkoutType.STRETCHING),
    (SDKWorkoutType.FLEXIBILITY, WorkoutType.STRETCHING),
    (SDKWorkoutType.COOLDOWN, WorkoutType.STRETCHING),
    # Studio Activities
    (SDKWorkoutType.BARRE, WorkoutType.AEROBICS),
    (SDKWorkoutType.CARDIO_DANCE, WorkoutType.DANCE),
    (SDKWorkoutType.SOCIAL_DANCE, WorkoutType.DANCE),
    (SDKWorkoutType.YOGA, WorkoutType.YOGA),
    (SDKWorkoutType.MIND_AND_BODY, WorkoutType.STRETCHING),
    (SDKWorkoutType.PILATES, WorkoutType.PILATES),
    # Team Sports
    (SDKWorkoutType.AMERICAN_FOOTBALL, WorkoutType.AMERICAN_FOOTBALL),
    (SDKWorkoutType.AUSTRALIAN_FOOTBALL, WorkoutType.FOOTBALL),
    (SDKWorkoutType.BASEBALL, WorkoutType.BASEBALL),
    (SDKWorkoutType.BASKETBALL, WorkoutType.BASKETBALL),
    (SDKWorkoutType.CRICKET, WorkoutType.OTHER),
    (SDKWorkoutType.DISC_SPORTS, WorkoutType.OTHER),
    (SDKWorkoutType.HANDBALL, WorkoutType.HANDBALL),
    (SDKWorkoutType.HOCKEY, WorkoutType.HOCKEY),
    (SDKWorkoutType.LACROSSE, WorkoutType.OTHER),
    (SDKWorkoutType.RUGBY, WorkoutType.RUGBY),
    (SDKWorkoutType.SOCCER, WorkoutType.SOCCER),
    (SDKWorkoutType.SOFTBALL, WorkoutType.BASEBALL),
    (SDKWorkoutType.VOLLEYBALL, WorkoutType.VOLLEYBALL),
    # Racket Sports
    (SDKWorkoutType.BADMINTON, WorkoutType.BADMINTON),
    (SDKWorkoutType.PICKLEBALL, WorkoutType.PICKLEBALL),
    (SDKWorkoutType.RACQUETBALL, WorkoutType.OTHER),
    (SDKWorkoutType.SQUASH, WorkoutType.SQUASH),
    (SDKWorkoutType.TABLE_TENNIS, WorkoutType.TABLE_TENNIS),
    (SDKWorkoutType.TENNIS, WorkoutType.TENNIS),
    # Outdoor Activities
    (SDKWorkoutType.CLIMBING, WorkoutType.ROCK_CLIMBING),
    (SDKWorkoutType.EQUESTRIAN, WorkoutType.HORSEBACK_RIDING),
    (SDKWorkoutType.FISHING, WorkoutType.OTHER),
    (SDKWorkoutType.GOLF, WorkoutType.GOLF),
    (SDKWorkoutType.HIKING, WorkoutType.HIKING),
    (SDKWorkoutType.HUNTING, WorkoutType.OTHER),
    (SDKWorkoutType.PLAY, WorkoutType.OTHER),
    # Snow and Ice Sports
    (SDKWorkoutType.CROSS_COUNTRY_SKIING, WorkoutType.CROSS_COUNTRY_SKIING),
    (SDKWorkoutType.CURLING, WorkoutType.OTHER),
    (SDKWorkoutType.DOWNHILL_SKIING, WorkoutType.ALPINE_SKIING),
    (SDKWorkoutType.SNOW_SPORTS, WorkoutType.OTHER),
    (SDKWorkoutType.SNOWBOARDING, WorkoutType.SNOWBOARDING),
    (SDKWorkoutType.SKATING, WorkoutType.ICE_SKATING),
    # Water Activities
    (SDKWorkoutType.PADDLE_SPORTS, WorkoutType.PADDLING),
    (SDKWorkoutType.ROWING, WorkoutType.ROWING),
    (SDKWorkoutType.SAILING, WorkoutType.SAILING),
    (SDKWorkoutType.SURFING, WorkoutType.SURFING),
    (SDKWorkoutType.SWIMMING, WorkoutType.SWIMMING),
    (SDKWorkoutType.UNDERWATER_DIVING, WorkoutType.DIVING),
    (SDKWorkoutType.WATER_FITNESS, WorkoutType.SWIMMING),
    (SDKWorkoutType.WATER_POLO, WorkoutType.OTHER),
    (SDKWorkoutType.WATER_SPORTS, WorkoutType.OTHER),
    # Martial Arts
    (SDKWorkoutType.BOXING, WorkoutType.BOXING),
    (SDKWorkoutType.KICKBOXING, WorkoutType.BOXING),
    (SDKWorkoutType.MARTIAL_ARTS, WorkoutType.MARTIAL_ARTS),
    (SDKWorkoutType.TAI_CHI, WorkoutType.MARTIAL_ARTS),
    (SDKWorkoutType.WRESTLING, WorkoutType.MARTIAL_ARTS),
    # Individual Sports
    (SDKWorkoutType.ARCHERY, WorkoutType.OTHER),
    (SDKWorkoutType.BOWLING, WorkoutType.OTHER),
    (SDKWorkoutType.FENCING, WorkoutType.OTHER),
    (SDKWorkoutType.GYMNASTICS, WorkoutType.FITNESS_EQUIPMENT),
    (SDKWorkoutType.TRACK_AND_FIELD, WorkoutType.RUNNING),
    # Multisport Activities
    (SDKWorkoutType.SWIM_BIKE_RUN, WorkoutType.TRIATHLON),
    (SDKWorkoutType.TRANSITION, WorkoutType.TRANSITION),
    # Deprecated (but still supported for backward compatibility)
    (SDKWorkoutType.DANCE, WorkoutType.DANCE),
    (SDKWorkoutType.DANCE_INSPIRED_TRAINING, WorkoutType.DANCE),
    (SDKWorkoutType.MIXED_METABOLIC_CARDIO_TRAINING, WorkoutType.CARDIO_TRAINING),
    # Health Connect (Android) — third-party HC writers (Peloton, Strava,
    # Zwift, …) emit these via ``HealthConnectManager.mapExerciseType`` in
    # the OW Android SDK. Wire format is uppercase (``"CYCLING_STATIONARY"``);
    # ``get_unified_workout_type`` lowercases input before lookup so the
    # snake_case keys below match.
    (SDKWorkoutType.CYCLING_STATIONARY, WorkoutType.INDOOR_CYCLING),
    (SDKWorkoutType.BOOT_CAMP, WorkoutType.CARDIO_TRAINING),
    (SDKWorkoutType.CALISTHENICS, WorkoutType.STRENGTH_TRAINING),
    (SDKWorkoutType.DANCING, WorkoutType.DANCE),
    (SDKWorkoutType.EXERCISE_CLASS, WorkoutType.CARDIO_TRAINING),
    (SDKWorkoutType.FOOTBALL_AMERICAN, WorkoutType.AMERICAN_FOOTBALL),
    (SDKWorkoutType.FOOTBALL_AUSTRALIAN, WorkoutType.FOOTBALL),
    (SDKWorkoutType.FRISBEE_DISC, WorkoutType.OTHER),
    (SDKWorkoutType.GUIDED_BREATHING, WorkoutType.MEDITATION),
    (SDKWorkoutType.ICE_HOCKEY, WorkoutType.HOCKEY),
    (SDKWorkoutType.ICE_SKATING, WorkoutType.ICE_SKATING),
    (SDKWorkoutType.PADDLING, WorkoutType.PADDLING),
    (SDKWorkoutType.PARAGLIDING, WorkoutType.OTHER),
    (SDKWorkoutType.ROCK_CLIMBING, WorkoutType.ROCK_CLIMBING),
    (SDKWorkoutType.ROLLER_HOCKEY, WorkoutType.HOCKEY),
    (SDKWorkoutType.ROWING_MACHINE, WorkoutType.ROWING_MACHINE),
    (SDKWorkoutType.RUNNING_TREADMILL, WorkoutType.TREADMILL),
    (SDKWorkoutType.SCUBA_DIVING, WorkoutType.OTHER),
    (SDKWorkoutType.SKIING, WorkoutType.ALPINE_SKIING),
    (SDKWorkoutType.SNOWSHOEING, WorkoutType.SNOWSHOEING),
    (SDKWorkoutType.STAIR_CLIMBING_MACHINE, WorkoutType.STAIR_CLIMBING),
    (SDKWorkoutType.STRETCHING, WorkoutType.STRETCHING),
    (SDKWorkoutType.SWIMMING_OPEN_WATER, WorkoutType.OPEN_WATER_SWIMMING),
    (SDKWorkoutType.SWIMMING_POOL, WorkoutType.POOL_SWIMMING),
    (SDKWorkoutType.WEIGHTLIFTING, WorkoutType.STRENGTH_TRAINING),
    (SDKWorkoutType.WHEELCHAIR, WorkoutType.OTHER),
    # Other
    (SDKWorkoutType.OTHER, WorkoutType.OTHER),
]


SDK_TO_UNIFIED: dict[SDKWorkoutType, WorkoutType] = {
    activity_type: unified_type for activity_type, unified_type in SDK_WORKOUT_TYPE_MAPPINGS
}


def get_unified_workout_type(sdk_activity_type: SDKWorkoutType | str) -> WorkoutType:
    """
    Convert SDK activity type to unified WorkoutType.

    Args:
        sdk_activity_type: SDK activity type string. Accepts both Apple
            HealthKit snake_case (``"running"``) and Health Connect
            uppercase vocabulary (``"CYCLING_STATIONARY"``) emitted by the
            OW Android SDK's ``HealthConnectManager.mapExerciseType``.

    Returns:
        Unified WorkoutType enum value

    Examples:
        >>> get_unified_workout_type("running")
        WorkoutType.RUNNING
        >>> get_unified_workout_type("cycling")
        WorkoutType.CYCLING
        >>> get_unified_workout_type("yoga")
        WorkoutType.YOGA
        >>> get_unified_workout_type("CYCLING_STATIONARY")
        WorkoutType.INDOOR_CYCLING
        >>> get_unified_workout_type("other")
        WorkoutType.OTHER
    Note:
        Some deprecated types are still supported for backward compatibility:
        - dance
        - dance_inspired_training
        - mixed_metabolic_cardio_training
    """
    # Normalise so we accept both Apple HealthKit (snake_case) and Health
    # Connect (UPPER_CASE) vocabulary on the wire. Strip whitespace because
    # some upstream writers pad the value.
    if isinstance(sdk_activity_type, str):
        normalised: SDKWorkoutType | str = sdk_activity_type.strip().lower()
    else:
        normalised = sdk_activity_type
    return SDK_TO_UNIFIED.get(normalised, WorkoutType.OTHER)  # type: ignore[arg-type]


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
