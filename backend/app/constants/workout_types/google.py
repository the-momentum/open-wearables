from app.schemas.enums import WorkoutType

# Google Health API Exercise.ExerciseType -> unified WorkoutType.
# Source: Google Health API Exercise.ExerciseType enum.
# Values with no close unified match are omitted and fall through to OTHER.
GOOGLE_EXERCISE_TYPE_MAPPINGS: list[tuple[str, WorkoutType]] = [
    # Running & walking
    ("RUNNING", WorkoutType.RUNNING),
    ("TRAIL_RUN", WorkoutType.TRAIL_RUNNING),
    ("INCLINE_RUN", WorkoutType.RUNNING),
    ("TREADMILL", WorkoutType.TREADMILL),
    ("WALKING", WorkoutType.WALKING),
    ("INCLINE_WALK", WorkoutType.WALKING),
    ("NORDIC_WALKING", WorkoutType.WALKING),
    ("STROLLER_WALK", WorkoutType.WALKING),
    ("TREADMILL_WALK", WorkoutType.TREADMILL),
    ("POWER_WALKING", WorkoutType.WALKING_FITNESS),
    ("WALK_WITH_WEIGHTS", WorkoutType.WALKING_FITNESS),
    ("RUCKING", WorkoutType.HIKING),
    ("HIKING", WorkoutType.HIKING),
    ("BACKPACKING", WorkoutType.HIKING),
    # Cycling
    ("BIKING", WorkoutType.CYCLING),
    ("OUTDOOR_BIKE", WorkoutType.CYCLING),
    ("HAND_CYCLING", WorkoutType.CYCLING),
    ("UNICYCLING", WorkoutType.CYCLING),
    ("MOUNTAIN_BIKE", WorkoutType.MOUNTAIN_BIKING),
    ("STATIONARY_BIKE", WorkoutType.INDOOR_CYCLING),
    ("ASSAULT_BIKE", WorkoutType.INDOOR_CYCLING),
    ("SPINNING", WorkoutType.INDOOR_CYCLING),
    ("ELECTRIC_BIKE", WorkoutType.E_BIKING),
    # Swimming & water
    ("SWIMMING", WorkoutType.SWIMMING),
    ("SWIMMING_POOL", WorkoutType.POOL_SWIMMING),
    ("SWIMMING_OPEN_WATER", WorkoutType.OPEN_WATER_SWIMMING),
    ("SYNCHRONIZED_SWIMMING", WorkoutType.SWIMMING),
    ("ROWING", WorkoutType.ROWING),
    ("ROWING_MACHINE", WorkoutType.ROWING_MACHINE),
    ("KAYAKING", WorkoutType.KAYAKING),
    ("CANOEING", WorkoutType.CANOEING),
    ("PADDLEBOARDING", WorkoutType.STAND_UP_PADDLEBOARDING),
    ("SURFING", WorkoutType.SURFING),
    ("FOILING", WorkoutType.WATER_SPORTS),
    ("KITESURFING", WorkoutType.KITESURFING),
    ("WINDSURFING", WorkoutType.WINDSURFING),
    ("SAILING", WorkoutType.SAILING),
    ("WAKEBOARDING", WorkoutType.WAKEBOARDING),
    ("WATER_SKIING", WorkoutType.WATER_SKIING),
    ("WATER_POLO", WorkoutType.WATER_POLO),
    ("WATER_AEROBICS", WorkoutType.WATER_SPORTS),
    ("WATER_JOGGING", WorkoutType.WATER_SPORTS),
    ("WATER_VOLLEYBALL", WorkoutType.WATER_SPORTS),
    ("WATER_SPORT", WorkoutType.WATER_SPORTS),
    # Strength & gym
    ("STRENGTH_TRAINING", WorkoutType.STRENGTH_TRAINING),
    ("FUNCTIONAL_STRENGTH_TRAINING", WorkoutType.STRENGTH_TRAINING),
    ("CORE_TRAINING", WorkoutType.STRENGTH_TRAINING),
    ("BODY_WEIGHT", WorkoutType.STRENGTH_TRAINING),
    ("CALISTHENICS", WorkoutType.STRENGTH_TRAINING),
    ("POWERLIFTING", WorkoutType.STRENGTH_TRAINING),
    ("WEIGHTLIFTING", WorkoutType.STRENGTH_TRAINING),
    ("FREE_WEIGHTS", WorkoutType.STRENGTH_TRAINING),
    ("WEIGHTS", WorkoutType.STRENGTH_TRAINING),
    ("WEIGHT_MACHINES", WorkoutType.STRENGTH_TRAINING),
    ("RESISTANCE_BANDS", WorkoutType.STRENGTH_TRAINING),
    ("TRX", WorkoutType.STRENGTH_TRAINING),
    ("CROSSFIT", WorkoutType.STRENGTH_TRAINING),
    ("ELLIPTICAL", WorkoutType.ELLIPTICAL),
    ("STAIRCLIMBER", WorkoutType.STAIR_CLIMBING),
    ("STEP_TRAINING", WorkoutType.STAIR_CLIMBING),
    ("JUMPING_ROPE", WorkoutType.CARDIO_TRAINING),
    # Cardio & class formats
    ("AEROBIC_WORKOUT", WorkoutType.AEROBICS),
    ("CARDIO_WORKOUT", WorkoutType.CARDIO_TRAINING),
    ("CARDIO_SCULPT", WorkoutType.CARDIO_TRAINING),
    ("HIIT", WorkoutType.CARDIO_TRAINING),
    ("TABATA_WORKOUT", WorkoutType.CARDIO_TRAINING),
    ("INTERVAL_WORKOUT", WorkoutType.CARDIO_TRAINING),
    ("CIRCUIT_TRAINING", WorkoutType.CARDIO_TRAINING),
    ("CROSS_TRAINING", WorkoutType.CARDIO_TRAINING),
    ("BOOTCAMP", WorkoutType.CARDIO_TRAINING),
    ("FITNESS_GAMING", WorkoutType.GAMING),
    ("EXERCISE_CLASS", WorkoutType.GROUP_EXERCISE),
    ("BARRE_CLASS", WorkoutType.GROUP_EXERCISE),
    ("OUTDOOR_WORKOUT", WorkoutType.GENERIC),
    ("WORKOUT", WorkoutType.GENERIC),
    # Flexibility & mind-body
    ("YOGA", WorkoutType.YOGA),
    ("YOGA_BIKRAM", WorkoutType.YOGA),
    ("YOGA_HATHA", WorkoutType.YOGA),
    ("YOGA_POWER", WorkoutType.YOGA),
    ("YOGA_VINYASA", WorkoutType.YOGA),
    ("PILATES", WorkoutType.PILATES),
    ("STRETCHING", WorkoutType.STRETCHING),
    ("MEDITATE", WorkoutType.MEDITATION),
    ("TAI_CHI", WorkoutType.MARTIAL_ARTS),
    # Winter sports
    ("SKIING", WorkoutType.DOWNHILL_SKIING),
    ("CROSS_COUNTRY_SKI", WorkoutType.CROSS_COUNTRY_SKIING),
    ("SNOWBOARDING", WorkoutType.SNOWBOARDING),
    ("SNOWSHOEING", WorkoutType.SNOWSHOEING),
    ("SNOWMOBILING", WorkoutType.SNOWMOBILING),
    ("ICE_SKATING", WorkoutType.ICE_SKATING),
    ("SPEED_SKATING", WorkoutType.ICE_SKATING),
    ("SNOW_SPORT", WorkoutType.SNOW_SPORTS),
    # Team sports
    ("SOCCER", WorkoutType.SOCCER),
    ("BASKETBALL", WorkoutType.BASKETBALL),
    ("BASEBALL", WorkoutType.BASEBALL),
    ("SOFTBALL", WorkoutType.BASEBALL),
    ("FOOTBALL_AMERICAN", WorkoutType.AMERICAN_FOOTBALL),
    ("FOOTBALL_AUSTRALIAN", WorkoutType.FOOTBALL),
    ("VOLLEYBALL", WorkoutType.VOLLEYBALL),
    ("VOLLEYBALL_BEACH", WorkoutType.VOLLEYBALL),
    ("HANDBALL", WorkoutType.HANDBALL),
    ("RUGBY", WorkoutType.RUGBY),
    ("HOCKEY", WorkoutType.HOCKEY),
    ("FIELD_HOCKEY", WorkoutType.HOCKEY),
    ("LACROSSE", WorkoutType.LACROSSE),
    ("CRICKET", WorkoutType.CRICKET),
    # Racket sports
    ("TENNIS", WorkoutType.TENNIS),
    ("TABLE_TENNIS", WorkoutType.TABLE_TENNIS),
    ("BADMINTON", WorkoutType.BADMINTON),
    ("SQUASH", WorkoutType.SQUASH),
    ("PADEL", WorkoutType.PADEL),
    ("PICKELBALL", WorkoutType.PICKLEBALL),
    ("RACQUETBALL", WorkoutType.RACQUETBALL),
    ("RACKET_SPORTS", WorkoutType.RACKET_SPORTS),
    # Combat sports
    ("BOXING", WorkoutType.BOXING),
    ("KICKBOXING", WorkoutType.MARTIAL_ARTS),
    ("MARTIAL_ARTS", WorkoutType.MARTIAL_ARTS),
    ("JIU_JITSU", WorkoutType.MARTIAL_ARTS),
    ("KARATE", WorkoutType.MARTIAL_ARTS),
    ("TAEKWONDO", WorkoutType.MARTIAL_ARTS),
    ("MUAY_THAI", WorkoutType.MARTIAL_ARTS),
    ("WRESTLING", WorkoutType.WRESTLING),
    ("FENCING", WorkoutType.FENCING),
    # Climbing & outdoor
    ("CLIMBING", WorkoutType.ROCK_CLIMBING),
    ("ROCK_CLIMBING", WorkoutType.ROCK_CLIMBING),
    ("INDOOR_CLIMBING", WorkoutType.INDOOR_CLIMBING),
    ("ORIENTEERING", WorkoutType.ORIENTEERING),
    ("ARCHERY", WorkoutType.ARCHERY),
    ("FISHING", WorkoutType.FISHING),
    ("HUNTING", WorkoutType.HUNTING),
    ("PARAGLIDING", WorkoutType.PARAGLIDING),
    ("PARKOUR", WorkoutType.PARKOUR),
    ("EQUESTRIAN_SPORTS", WorkoutType.HORSEBACK_RIDING),
    # Other sports
    ("GOLF", WorkoutType.GOLF),
    ("SKATING", WorkoutType.SKATING),
    ("ROLLER_SKATING", WorkoutType.SKATING),
    ("ROLLERBLADING", WorkoutType.INLINE_SKATING),
    ("SKATEBOARDING", WorkoutType.SKATEBOARDING),
    ("GYMNASTICS", WorkoutType.GYMNASTICS),
    ("TRAMPOLINE", WorkoutType.GYMNASTICS),
    ("CHEERLEADING", WorkoutType.GYMNASTICS),
    ("BOWLING", WorkoutType.BOWLING),
    ("CURLING", WorkoutType.CURLING),
    ("FRISBEE_PLAYING_GENERAL", WorkoutType.DISC_SPORTS),
    ("ULTIMATE_FRISBEE", WorkoutType.DISC_SPORTS),
    ("TRACK_AND_FIELD", WorkoutType.SPORT),
    ("SPORT", WorkoutType.SPORT),
    ("MULTISPORT", WorkoutType.MULTISPORT),
    # Dance
    ("DANCING", WorkoutType.DANCE),
    ("BALLET", WorkoutType.DANCE),
    ("BALLROOM_DANCE", WorkoutType.DANCE),
    ("BREAKDANCING", WorkoutType.DANCE),
    ("HIP_HOP", WorkoutType.DANCE),
    ("JAZZ_DANCE", WorkoutType.DANCE),
    ("MODERN_DANCE", WorkoutType.DANCE),
    ("TANGO", WorkoutType.DANCE),
    ("ZUMBA", WorkoutType.DANCE),
    # Motor sports
    ("MOTORCYCLE", WorkoutType.MOTORCYCLING),
    ("MOTOCROSS", WorkoutType.MOTOR_SPORTS),
    # Diving
    ("DIVING", WorkoutType.DIVING),
    ("SCUBA_DIVING", WorkoutType.DIVING),
    ("SNORKELING", WorkoutType.SNORKELING),
    # Wheelchair
    ("WHEELCHAIR", WorkoutType.WHEELCHAIR),
    # Lifestyle & chores
    ("CLEANING", WorkoutType.CHORES),
    ("HOUSEHOLD_CHORES", WorkoutType.CHORES),
    ("GARDENING", WorkoutType.CHORES),
    ("MOWING_LAWN", WorkoutType.CHORES),
    ("SHOVELING", WorkoutType.CHORES),
    ("WEEDING", WorkoutType.CHORES),
    ("HOEING", WorkoutType.CHORES),
    ("CARPENTRY", WorkoutType.CHORES),
    # Generic / unspecified
    ("OTHER", WorkoutType.OTHER),
    ("EXERCISE_TYPE_UNSPECIFIED", WorkoutType.OTHER),
]

# Lookup dictionary
GOOGLE_EXERCISE_TO_UNIFIED: dict[str, WorkoutType] = dict(GOOGLE_EXERCISE_TYPE_MAPPINGS)


def get_unified_workout_type(google_exercise_type: str) -> WorkoutType:
    """Convert a Google Health API Exercise.ExerciseType to a unified WorkoutType.

    Google uses UPPER_SNAKE_CASE. Unmapped/niche types fall through to OTHER.

    Examples:
        >>> get_unified_workout_type("RUNNING")
        WorkoutType.RUNNING
        >>> get_unified_workout_type("STATIONARY_BIKE")
        WorkoutType.INDOOR_CYCLING
        >>> get_unified_workout_type("BILLIARDS")
        WorkoutType.OTHER
    """
    normalized = google_exercise_type.upper().strip()
    return GOOGLE_EXERCISE_TO_UNIFIED.get(normalized, WorkoutType.OTHER)
