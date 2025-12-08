from app.schemas.workout_types import WorkoutType

# Polar uses two fields: 'sport' (basic category) and 'detailed_sport_info' (specific activity)
# Format: (polar_sport_value, polar_detailed_sport_info, unified_type)
POLAR_WORKOUT_TYPE_MAPPINGS: list[tuple[str, str | None, WorkoutType]] = [
    # Running variants - sport="RUNNING"
    ("RUNNING", None, WorkoutType.RUNNING),
    ("RUNNING", "RUNNING_ROAD", WorkoutType.RUNNING),
    ("RUNNING", "RUNNING_TRAIL", WorkoutType.TRAIL_RUNNING),
    ("RUNNING", "RUNNING_TREADMILL", WorkoutType.TREADMILL),
    # Cycling variants - sport="CYCLING" or "OTHER"
    ("CYCLING", None, WorkoutType.CYCLING),
    ("CYCLING", "CYCLING_ROAD", WorkoutType.CYCLING),
    ("CYCLING", "CYCLING_MOUNTAIN", WorkoutType.MOUNTAIN_BIKING),
    ("CYCLING", "CYCLING_INDOOR", WorkoutType.INDOOR_CYCLING),
    ("OTHER", "CYCLING_MOUNTAIN_BIKE", WorkoutType.MOUNTAIN_BIKING),
    ("OTHER", "CYCLING_CYCLOCROSS", WorkoutType.CYCLOCROSS),
    # Swimming - sport="SWIMMING" or "OTHER"
    ("SWIMMING", None, WorkoutType.SWIMMING),
    ("SWIMMING", "SWIMMING_POOL", WorkoutType.POOL_SWIMMING),
    ("SWIMMING", "SWIMMING_OPEN_WATER", WorkoutType.OPEN_WATER_SWIMMING),
    ("OTHER", "AQUATICS_SWIMMING", WorkoutType.SWIMMING),
    # Walking & Hiking - sport="WALKING" or "OTHER"
    ("WALKING", None, WorkoutType.WALKING),
    ("OTHER", "WALKING", WorkoutType.WALKING),
    ("OTHER", "WALKING_NORDIC", WorkoutType.WALKING),
    ("OTHER", "HIKING", WorkoutType.HIKING),
    ("OTHER", "MOUNTAINEERING", WorkoutType.MOUNTAINEERING),
    # Winter Sports - sport="OTHER"
    ("OTHER", "WINTERSPORTS_CROSS_COUNTRY_SKIING", WorkoutType.CROSS_COUNTRY_SKIING),
    ("OTHER", "WINTERSPORTS_ALPINE_SKIING", WorkoutType.ALPINE_SKIING),
    ("OTHER", "WINTERSPORTS_BACKCOUNTRY_SKIING", WorkoutType.BACKCOUNTRY_SKIING),
    ("OTHER", "WINTERSPORTS_DOWNHILL_SKIING", WorkoutType.ALPINE_SKIING),
    ("OTHER", "WINTERSPORTS_SNOWBOARDING", WorkoutType.SNOWBOARDING),
    ("OTHER", "WINTERSPORTS_SNOWSHOEING", WorkoutType.SNOWSHOEING),
    ("OTHER", "WINTERSPORTS_ICE_SKATING", WorkoutType.ICE_SKATING),
    # Strength & Gym - sport="STRENGTH_TRAINING" or "OTHER"
    ("STRENGTH_TRAINING", None, WorkoutType.STRENGTH_TRAINING),
    ("OTHER", "FITNESS_CARDIO", WorkoutType.CARDIO_TRAINING),
    ("OTHER", "FITNESS_ELLIPTICAL", WorkoutType.ELLIPTICAL),
    ("OTHER", "FITNESS_INDOOR_ROWING", WorkoutType.ROWING_MACHINE),
    ("OTHER", "FITNESS_STAIR_CLIMBING", WorkoutType.STAIR_CLIMBING),
    # Water Sports - sport="OTHER"
    ("OTHER", "WATERSPORTS_ROWING", WorkoutType.ROWING),
    ("OTHER", "WATERSPORTS_KAYAKING", WorkoutType.KAYAKING),
    ("OTHER", "WATERSPORTS_CANOEING", WorkoutType.CANOEING),
    ("OTHER", "WATERSPORTS_STAND_UP_PADDLING", WorkoutType.STAND_UP_PADDLEBOARDING),
    ("OTHER", "WATERSPORTS_SURFING", WorkoutType.SURFING),
    ("OTHER", "WATERSPORTS_KITESURFING", WorkoutType.KITESURFING),
    ("OTHER", "WATERSPORTS_WINDSURFING", WorkoutType.WINDSURFING),
    ("OTHER", "WATERSPORTS_SAILING", WorkoutType.SAILING),
    ("OTHER", "WATERSPORTS_WATERSKI", WorkoutType.OTHER),
    # Team Sports - sport="BASKETBALL", "SOCCER", etc. or "OTHER"
    ("BASKETBALL", None, WorkoutType.BASKETBALL),
    ("SOCCER", None, WorkoutType.SOCCER),
    ("OTHER", "TEAMSPORTS_SOCCER", WorkoutType.SOCCER),
    ("OTHER", "TEAMSPORTS_FOOTBALL", WorkoutType.FOOTBALL),
    ("OTHER", "TEAMSPORTS_AMERICAN_FOOTBALL", WorkoutType.AMERICAN_FOOTBALL),
    ("OTHER", "TEAMSPORTS_BASEBALL", WorkoutType.BASEBALL),
    ("OTHER", "TEAMSPORTS_BASKETBALL", WorkoutType.BASKETBALL),
    ("OTHER", "TEAMSPORTS_VOLLEYBALL", WorkoutType.VOLLEYBALL),
    ("OTHER", "TEAMSPORTS_HANDBALL", WorkoutType.HANDBALL),
    ("OTHER", "TEAMSPORTS_RUGBY", WorkoutType.RUGBY),
    ("OTHER", "TEAMSPORTS_HOCKEY", WorkoutType.HOCKEY),
    ("OTHER", "TEAMSPORTS_FLOORBALL", WorkoutType.FLOORBALL),
    # Racket Sports - sport="TENNIS" or "OTHER"
    ("TENNIS", None, WorkoutType.TENNIS),
    ("OTHER", "RACKET_SPORTS_TENNIS", WorkoutType.TENNIS),
    ("OTHER", "RACKET_SPORTS_BADMINTON", WorkoutType.BADMINTON),
    ("OTHER", "RACKET_SPORTS_SQUASH", WorkoutType.SQUASH),
    ("OTHER", "RACKET_SPORTS_TABLE_TENNIS", WorkoutType.TABLE_TENNIS),
    ("OTHER", "RACKET_SPORTS_PADEL", WorkoutType.PADEL),
    # Mind-Body - sport="OTHER"
    ("OTHER", "FITNESS_YOGA", WorkoutType.YOGA),
    ("OTHER", "FITNESS_PILATES", WorkoutType.PILATES),
    ("OTHER", "FITNESS_STRETCHING", WorkoutType.STRETCHING),
    # Combat Sports - sport="OTHER"
    ("OTHER", "COMBAT_SPORTS_BOXING", WorkoutType.BOXING),
    ("OTHER", "COMBAT_SPORTS_MARTIAL_ARTS", WorkoutType.MARTIAL_ARTS),
    # Outdoor Activities - sport="OTHER"
    ("OTHER", "OUTDOOR_CLIMBING", WorkoutType.ROCK_CLIMBING),
    ("OTHER", "INDOOR_CLIMBING", WorkoutType.INDOOR_CLIMBING),
    ("OTHER", "ORIENTEERING", WorkoutType.ORIENTEERING),
    # Other Sports - sport="OTHER"
    ("OTHER", "GOLF", WorkoutType.GOLF),
    ("OTHER", "INLINE_SKATING", WorkoutType.INLINE_SKATING),
    ("OTHER", "SKATEBOARDING", WorkoutType.SKATEBOARDING),
    ("OTHER", "HORSEBACK_RIDING", WorkoutType.HORSEBACK_RIDING),
    # Multisport
    ("MULTISPORT", None, WorkoutType.MULTISPORT),
    ("OTHER", "TRIATHLON", WorkoutType.TRIATHLON),
    # Motor Sports
    ("OTHER", "MOTORSPORTS", WorkoutType.MOTORCYCLING),
    # Dance
    ("OTHER", "DANCE", WorkoutType.DANCE),
    # Generic/Other
    ("OTHER", None, WorkoutType.OTHER),
]


POLAR_TO_UNIFIED: dict[tuple[str, str | None], WorkoutType] = {
    (sport, detailed): unified_type for sport, detailed, unified_type in POLAR_WORKOUT_TYPE_MAPPINGS
}


def get_unified_workout_type(polar_sport: str, polar_detailed_sport_info: str | None = None) -> WorkoutType:
    """
    Convert Polar sport types to unified WorkoutType.

    Args:
        polar_sport: Polar 'sport' field (e.g., "RUNNING", "OTHER")
        polar_detailed_sport_info: Polar 'detailed_sport_info' field (optional)

    Returns:
        Unified WorkoutType enum value
    """
    # Try exact match first (with detailed_sport_info)
    if polar_detailed_sport_info:
        key = (polar_sport, polar_detailed_sport_info)
        if key in POLAR_TO_UNIFIED:
            return POLAR_TO_UNIFIED[key]

    # Fall back to sport-only match
    key = (polar_sport, None)
    if key in POLAR_TO_UNIFIED:
        return POLAR_TO_UNIFIED[key]

    # Default to OTHER
    return WorkoutType.OTHER
