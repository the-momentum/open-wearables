from app.schemas.workout_types import WorkoutType

# Garmin Wellness/Health API activity types from official specification
# Source: Garmin Health API Specification - Appendix A
# Format: (garmin_api_value, unified_type)
GARMIN_WELLNESS_WORKOUT_TYPE_MAPPINGS: list[tuple[str, WorkoutType]] = [
    # Running
    ("RUNNING", WorkoutType.RUNNING),
    ("INDOOR_RUNNING", WorkoutType.TREADMILL),
    ("OBSTACLE_RUN", WorkoutType.RUNNING),
    ("STREET_RUNNING", WorkoutType.RUNNING),
    ("TRACK_RUNNING", WorkoutType.RUNNING),
    ("TRAIL_RUNNING", WorkoutType.TRAIL_RUNNING),
    ("TREADMILL_RUNNING", WorkoutType.TREADMILL),
    ("ULTRA_RUN", WorkoutType.RUNNING),
    ("VIRTUAL_RUN", WorkoutType.RUNNING),
    # Cycling
    ("CYCLING", WorkoutType.CYCLING),
    ("BMX", WorkoutType.CYCLING),
    ("CYCLOCROSS", WorkoutType.CYCLOCROSS),
    ("DOWNHILL_BIKING", WorkoutType.MOUNTAIN_BIKING),
    ("E_BIKE_FITNESS", WorkoutType.E_BIKING),
    ("E_BIKE_MOUNTAIN", WorkoutType.E_BIKING),
    ("E_ENDURO_MTB", WorkoutType.E_BIKING),
    ("ENDURO_MTB", WorkoutType.MOUNTAIN_BIKING),
    ("GRAVEL_CYCLING", WorkoutType.CYCLING),
    ("INDOOR_CYCLING", WorkoutType.INDOOR_CYCLING),
    ("MOUNTAIN_BIKING", WorkoutType.MOUNTAIN_BIKING),
    ("RECUMBENT_CYCLING", WorkoutType.CYCLING),
    ("ROAD_BIKING", WorkoutType.CYCLING),
    ("TRACK_CYCLING", WorkoutType.CYCLING),
    ("VIRTUAL_RIDE", WorkoutType.INDOOR_CYCLING),
    ("HANDCYCLING", WorkoutType.CYCLING),
    ("INDOOR_HANDCYCLING", WorkoutType.INDOOR_CYCLING),
    # Gym & Fitness Equipment
    ("FITNESS_EQUIPMENT", WorkoutType.FITNESS_EQUIPMENT),
    ("BOULDERING", WorkoutType.INDOOR_CLIMBING),
    ("ELLIPTICAL", WorkoutType.ELLIPTICAL),
    ("INDOOR_CARDIO", WorkoutType.CARDIO_TRAINING),
    ("HIIT", WorkoutType.CARDIO_TRAINING),
    ("INDOOR_CLIMBING", WorkoutType.INDOOR_CLIMBING),
    ("INDOOR_ROWING", WorkoutType.ROWING_MACHINE),
    ("MOBILITY", WorkoutType.STRETCHING),
    ("PILATES", WorkoutType.PILATES),
    ("STAIR_CLIMBING", WorkoutType.STAIR_CLIMBING),
    ("STRENGTH_TRAINING", WorkoutType.STRENGTH_TRAINING),
    ("YOGA", WorkoutType.YOGA),
    ("MEDITATION", WorkoutType.STRETCHING),
    # Swimming
    ("SWIMMING", WorkoutType.SWIMMING),
    ("LAP_SWIMMING", WorkoutType.POOL_SWIMMING),
    ("OPEN_WATER_SWIMMING", WorkoutType.OPEN_WATER_SWIMMING),
    # Walking & Hiking
    ("WALKING", WorkoutType.WALKING),
    ("CASUAL_WALKING", WorkoutType.WALKING),
    ("SPEED_WALKING", WorkoutType.WALKING),
    ("HIKING", WorkoutType.HIKING),
    ("RUCKING", WorkoutType.HIKING),
    # Winter Sports
    ("WINTER_SPORTS", WorkoutType.OTHER),
    ("BACKCOUNTRY_SNOWBOARDING", WorkoutType.SNOWBOARDING),
    ("BACKCOUNTRY_SKIING", WorkoutType.BACKCOUNTRY_SKIING),
    ("CROSS_COUNTRY_SKIING_WS", WorkoutType.CROSS_COUNTRY_SKIING),
    ("RESORT_SKIING", WorkoutType.ALPINE_SKIING),
    ("SNOWBOARDING_WS", WorkoutType.SNOWBOARDING),
    ("RESORT_SKIING_SNOWBOARDING_WS", WorkoutType.ALPINE_SKIING),
    ("SKATE_SKIING_WS", WorkoutType.CROSS_COUNTRY_SKIING),
    ("SKATING_WS", WorkoutType.ICE_SKATING),
    ("SNOW_SHOE_WS", WorkoutType.SNOWSHOEING),
    ("SNOWMOBILING_WS", WorkoutType.OTHER),
    # Water Sports (note: some have _V2 variants)
    ("WATER_SPORTS", WorkoutType.OTHER),
    ("BOATING_V2", WorkoutType.OTHER),
    ("BOATING", WorkoutType.OTHER),
    ("FISHING_V2", WorkoutType.OTHER),
    ("FISHING", WorkoutType.OTHER),
    ("KAYAKING_V2", WorkoutType.KAYAKING),
    ("KAYAKING", WorkoutType.KAYAKING),
    ("KITEBOARDING_V2", WorkoutType.KITESURFING),
    ("KITEBOARDING", WorkoutType.KITESURFING),
    ("OFFSHORE_GRINDING_V2", WorkoutType.SAILING),
    ("OFFSHORE_GRINDING", WorkoutType.SAILING),
    ("ONSHORE_GRINDING_V2", WorkoutType.SAILING),
    ("ONSHORE_GRINDING", WorkoutType.SAILING),
    ("PADDLING_V2", WorkoutType.PADDLING),
    ("PADDLING", WorkoutType.PADDLING),
    ("ROWING_V2", WorkoutType.ROWING),
    ("ROWING", WorkoutType.ROWING),
    ("SAILING_V2", WorkoutType.SAILING),
    ("SAILING", WorkoutType.SAILING),
    ("SNORKELING", WorkoutType.DIVING),
    ("STAND_UP_PADDLEBOARDING_V2", WorkoutType.STAND_UP_PADDLEBOARDING),
    ("STAND_UP_PADDLEBOARDING", WorkoutType.STAND_UP_PADDLEBOARDING),
    ("SURFING_V2", WorkoutType.SURFING),
    ("SURFING", WorkoutType.SURFING),
    ("WAKEBOARDING_V2", WorkoutType.OTHER),
    ("WAKEBOARDING", WorkoutType.OTHER),
    ("WATERSKIING", WorkoutType.OTHER),
    ("WHITEWATER_RAFTING_V2", WorkoutType.KAYAKING),
    ("WHITEWATER_RAFTING", WorkoutType.KAYAKING),
    ("WINDSURFING_V2", WorkoutType.WINDSURFING),
    ("WINDSURFING", WorkoutType.WINDSURFING),
    # Transitions
    ("TRANSITION_V2", WorkoutType.TRANSITION),
    ("BIKE_TO_RUN_TRANSITION_V2", WorkoutType.TRANSITION),
    ("BIKE_TO_RUN_TRANSITION", WorkoutType.TRANSITION),
    ("RUN_TO_BIKE_TRANSITION_V2", WorkoutType.TRANSITION),
    ("RUN_TO_BIKE_TRANSITION", WorkoutType.TRANSITION),
    ("SWIM_TO_BIKE_TRANSITION_V2", WorkoutType.TRANSITION),
    ("SWIM_TO_BIKE_TRANSITION", WorkoutType.TRANSITION),
    # Team Sports
    ("TEAM_SPORTS", WorkoutType.OTHER),
    ("AMERICAN_FOOTBALL", WorkoutType.AMERICAN_FOOTBALL),
    ("BASEBALL", WorkoutType.BASEBALL),
    ("BASKETBALL", WorkoutType.BASKETBALL),
    ("CRICKET", WorkoutType.OTHER),
    ("FIELD_HOCKEY", WorkoutType.HOCKEY),
    ("ICE_HOCKEY", WorkoutType.HOCKEY),
    ("LACROSSE", WorkoutType.OTHER),
    ("RUGBY", WorkoutType.RUGBY),
    ("SOCCER", WorkoutType.SOCCER),
    ("SOFTBALL", WorkoutType.BASEBALL),
    ("ULTIMATE_DISC", WorkoutType.OTHER),
    ("VOLLEYBALL", WorkoutType.VOLLEYBALL),
    # Racket Sports
    ("RACKET_SPORTS", WorkoutType.OTHER),
    ("BADMINTON", WorkoutType.BADMINTON),
    ("PADDELBALL", WorkoutType.PADEL),  # Note: Garmin spells it "PADDELBALL" for Padel
    ("PICKLEBALL", WorkoutType.OTHER),
    ("PLATFORM_TENNIS", WorkoutType.TENNIS),
    ("RACQUETBALL", WorkoutType.OTHER),
    ("SQUASH", WorkoutType.SQUASH),
    ("TABLE_TENNIS", WorkoutType.TABLE_TENNIS),
    ("TENNIS_V2", WorkoutType.TENNIS),
    ("TENNIS", WorkoutType.TENNIS),
    # Other
    ("OTHER", WorkoutType.OTHER),
    ("BOXING", WorkoutType.BOXING),
    ("BREATHWORK", WorkoutType.STRETCHING),
    ("DANCE", WorkoutType.DANCE),
    ("DISC_GOLF", WorkoutType.OTHER),
    ("FLOOR_CLIMBING", WorkoutType.STAIR_CLIMBING),
    ("GOLF", WorkoutType.GOLF),
    ("INLINE_SKATING", WorkoutType.INLINE_SKATING),
    ("JUMP_ROPE", WorkoutType.CARDIO_TRAINING),
    ("MIXED_MARTIAL_ARTS", WorkoutType.MARTIAL_ARTS),
    ("MOUNTAINEERING", WorkoutType.MOUNTAINEERING),
    ("ROCK_CLIMBING", WorkoutType.ROCK_CLIMBING),
    ("STOP_WATCH", WorkoutType.OTHER),
    ("PARA_SPORTS", WorkoutType.OTHER),
    ("WHEELCHAIR_PUSH_RUN", WorkoutType.RUNNING),
    ("WHEELCHAIR_PUSH_WALK", WorkoutType.WALKING),
]

# Create lookup dictionary
GARMIN_WELLNESS_TO_UNIFIED: dict[str, WorkoutType] = {
    activity_type: unified_type for activity_type, unified_type in GARMIN_WELLNESS_WORKOUT_TYPE_MAPPINGS
}


def get_unified_workout_type(garmin_activity_type: str) -> WorkoutType:
    """
    Convert Garmin Wellness API activity type to unified WorkoutType.

    Args:
        garmin_activity_type: Garmin activity type string (e.g., "RUNNING", "TRAIL_RUNNING")

    Returns:
        Unified WorkoutType enum value

    Examples:
        >>> get_unified_workout_type("RUNNING")
        WorkoutType.RUNNING
        >>> get_unified_workout_type("TRAIL_RUNNING")
        WorkoutType.TRAIL_RUNNING
        >>> get_unified_workout_type("INDOOR_CYCLING")
        WorkoutType.INDOOR_CYCLING
        >>> get_unified_workout_type("UNKNOWN_ACTIVITY")
        WorkoutType.OTHER

    Note:
        Some Garmin activities have _V2 variants (e.g., BOATING and BOATING_V2).
        Both variants map to the same unified type.
    """
    # Garmin uses uppercase with underscores
    normalized = garmin_activity_type.upper().strip()
    return GARMIN_WELLNESS_TO_UNIFIED.get(normalized, WorkoutType.OTHER)
