from app.schemas.workout_types import WorkoutType

# Strava API sport_type values mapped to unified WorkoutType.
# Strava uses PascalCase strings for sport_type (preferred over the legacy `type` field).
# Source: https://developers.strava.com/docs/reference/#api-models-SportType
# Format: (strava_sport_type, unified_type)
STRAVA_WORKOUT_TYPE_MAPPINGS: list[tuple[str, WorkoutType]] = [
    # Running
    ("Run", WorkoutType.RUNNING),
    ("TrailRun", WorkoutType.TRAIL_RUNNING),
    ("VirtualRun", WorkoutType.RUNNING),
    # Cycling
    ("Ride", WorkoutType.CYCLING),
    ("MountainBikeRide", WorkoutType.MOUNTAIN_BIKING),
    ("GravelRide", WorkoutType.CYCLING),
    ("EBikeRide", WorkoutType.E_BIKING),
    ("EMountainBikeRide", WorkoutType.E_BIKING),
    ("VirtualRide", WorkoutType.INDOOR_CYCLING),
    ("Velomobile", WorkoutType.CYCLING),
    ("Handcycle", WorkoutType.CYCLING),
    # Swimming
    ("Swim", WorkoutType.SWIMMING),
    # Walking & Hiking
    ("Walk", WorkoutType.WALKING),
    ("Hike", WorkoutType.HIKING),
    # Winter Sports
    ("AlpineSki", WorkoutType.ALPINE_SKIING),
    ("BackcountrySki", WorkoutType.BACKCOUNTRY_SKIING),
    ("NordicSki", WorkoutType.CROSS_COUNTRY_SKIING),
    ("Snowboard", WorkoutType.SNOWBOARDING),
    ("Snowshoe", WorkoutType.SNOWSHOEING),
    ("IceSkate", WorkoutType.ICE_SKATING),
    # Water Sports
    ("Rowing", WorkoutType.ROWING),
    ("Kayaking", WorkoutType.KAYAKING),
    ("Canoeing", WorkoutType.CANOEING),
    ("StandUpPaddling", WorkoutType.STAND_UP_PADDLEBOARDING),
    ("Surfing", WorkoutType.SURFING),
    ("Kitesurf", WorkoutType.KITESURFING),
    ("Windsurf", WorkoutType.WINDSURFING),
    ("Sail", WorkoutType.SAILING),
    # Gym & Fitness
    ("WeightTraining", WorkoutType.STRENGTH_TRAINING),
    ("Yoga", WorkoutType.YOGA),
    ("Pilates", WorkoutType.PILATES),
    ("Crossfit", WorkoutType.CARDIO_TRAINING),
    ("Elliptical", WorkoutType.ELLIPTICAL),
    ("StairStepper", WorkoutType.STAIR_CLIMBING),
    ("HIIT", WorkoutType.CARDIO_TRAINING),
    # Racket Sports
    ("Pickleball", WorkoutType.PICKLEBALL),
    ("Racquetball", WorkoutType.OTHER),
    ("Squash", WorkoutType.SQUASH),
    ("Badminton", WorkoutType.BADMINTON),
    ("TableTennis", WorkoutType.TABLE_TENNIS),
    ("Tennis", WorkoutType.TENNIS),
    # Team Sports
    ("Soccer", WorkoutType.SOCCER),
    ("Football", WorkoutType.AMERICAN_FOOTBALL),
    ("Baseball", WorkoutType.BASEBALL),
    ("Basketball", WorkoutType.BASKETBALL),
    ("Volleyball", WorkoutType.VOLLEYBALL),
    ("Hockey", WorkoutType.HOCKEY),
    ("Lacrosse", WorkoutType.LACROSSE),
    ("Rugby", WorkoutType.RUGBY),
    ("Cricket", WorkoutType.CRICKET),
    # Combat
    ("MartialArts", WorkoutType.MARTIAL_ARTS),
    # Outdoor
    ("RockClimbing", WorkoutType.ROCK_CLIMBING),
    ("Golf", WorkoutType.GOLF),
    ("Skateboard", WorkoutType.SKATEBOARDING),
    ("InlineSkate", WorkoutType.INLINE_SKATING),
    ("RollerSki", WorkoutType.CROSS_COUNTRY_SKIING),
    # Other
    ("Wheelchair", WorkoutType.OTHER),
    ("Workout", WorkoutType.OTHER),
    ("VirtualRow", WorkoutType.ROWING_MACHINE),
]

# Create lookup dictionary (case-sensitive, Strava uses PascalCase)
STRAVA_TO_UNIFIED: dict[str, WorkoutType] = {
    sport_type: unified_type for sport_type, unified_type in STRAVA_WORKOUT_TYPE_MAPPINGS
}


def get_unified_workout_type(strava_sport_type: str) -> WorkoutType:
    """Convert Strava sport_type to unified WorkoutType.

    Args:
        strava_sport_type: Strava sport type string (e.g., "Run", "TrailRun", "Ride")

    Returns:
        Unified WorkoutType enum value

    Examples:
        >>> get_unified_workout_type("Run")
        WorkoutType.RUNNING
        >>> get_unified_workout_type("TrailRun")
        WorkoutType.TRAIL_RUNNING
        >>> get_unified_workout_type("MountainBikeRide")
        WorkoutType.MOUNTAIN_BIKING
        >>> get_unified_workout_type("UnknownSport")
        WorkoutType.OTHER
    """
    return STRAVA_TO_UNIFIED.get(strava_sport_type, WorkoutType.OTHER)
