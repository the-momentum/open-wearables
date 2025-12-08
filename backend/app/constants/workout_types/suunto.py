from app.schemas.workout_types import WorkoutType

# Suunto uses integer activity IDs as documented in their Activities.pdf
# Format: (suunto_activity_id, activity_name, unified_type)
SUUNTO_WORKOUT_TYPE_MAPPINGS: list[tuple[int, str, WorkoutType]] = [
    # Core Activities (0-3)
    (0, "Walking", WorkoutType.WALKING),
    (1, "Running", WorkoutType.RUNNING),
    (2, "Cycling", WorkoutType.CYCLING),
    (3, "Cross-country skiing", WorkoutType.CROSS_COUNTRY_SKIING),
    
    # Generic Sports (4-9)
    (4, "Sports", WorkoutType.OTHER),
    (5, "Sports", WorkoutType.OTHER),
    (6, "Sports", WorkoutType.OTHER),
    (7, "Sports", WorkoutType.OTHER),
    (8, "Sports", WorkoutType.OTHER),
    (9, "Sports", WorkoutType.OTHER),
    
    # Outdoor Activities (10-31)
    (10, "Mountain biking", WorkoutType.MOUNTAIN_BIKING),
    (11, "Hiking", WorkoutType.HIKING),
    (12, "Roller skating", WorkoutType.INLINE_SKATING),
    (13, "Downhill skiing", WorkoutType.ALPINE_SKIING),
    (14, "Paddling", WorkoutType.PADDLING),
    (15, "Rowing", WorkoutType.ROWING),
    (16, "Golfing", WorkoutType.GOLF),
    (17, "Indoor sports", WorkoutType.FITNESS_EQUIPMENT),
    (18, "Parkouring", WorkoutType.OTHER),
    (19, "Ball games", WorkoutType.OTHER),
    (20, "Outdoor gym", WorkoutType.FITNESS_EQUIPMENT),
    (21, "Swimming", WorkoutType.SWIMMING),
    (22, "Trail running", WorkoutType.TRAIL_RUNNING),
    (23, "Gym", WorkoutType.STRENGTH_TRAINING),
    (24, "Nordic walking", WorkoutType.WALKING),
    (25, "Horseback riding", WorkoutType.HORSEBACK_RIDING),
    (26, "Motorsports", WorkoutType.MOTORCYCLING),
    (27, "Skateboarding", WorkoutType.SKATEBOARDING),
    (28, "Water sports", WorkoutType.OTHER),
    (29, "Climbing", WorkoutType.ROCK_CLIMBING),
    (30, "Snowboarding", WorkoutType.SNOWBOARDING),
    (31, "Ski touring", WorkoutType.BACKCOUNTRY_SKIING),
    
    # Team & Racket Sports (32-48)
    (32, "Fitness class", WorkoutType.AEROBICS),
    (33, "Soccer", WorkoutType.SOCCER),
    (34, "Tennis", WorkoutType.TENNIS),
    (35, "Basketball", WorkoutType.BASKETBALL),
    (36, "Badminton", WorkoutType.BADMINTON),
    (37, "Baseball", WorkoutType.BASEBALL),
    (38, "Volleyball", WorkoutType.VOLLEYBALL),
    (39, "American football", WorkoutType.AMERICAN_FOOTBALL),
    (40, "Table tennis", WorkoutType.TABLE_TENNIS),
    (41, "Racquet ball", WorkoutType.OTHER),
    (42, "Squash", WorkoutType.SQUASH),
    (43, "Floorball", WorkoutType.FLOORBALL),
    (44, "Handball", WorkoutType.HANDBALL),
    (45, "Softball", WorkoutType.BASEBALL),
    (46, "Bowling", WorkoutType.OTHER),
    (47, "Cricket", WorkoutType.OTHER),
    (48, "Rugby", WorkoutType.RUGBY),
    
    # Winter & Indoor (49-58)
    (49, "Ice skating", WorkoutType.ICE_SKATING),
    (50, "Ice hockey", WorkoutType.HOCKEY),
    (51, "Yoga/pilates", WorkoutType.YOGA),
    (52, "Indoor cycling", WorkoutType.INDOOR_CYCLING),
    (53, "Treadmill", WorkoutType.TREADMILL),
    (54, "Crossfit", WorkoutType.STRENGTH_TRAINING),
    (55, "Crosstrainer", WorkoutType.ELLIPTICAL),
    (56, "Roller skiing", WorkoutType.CROSS_COUNTRY_SKIING),
    (57, "Indoor rowing", WorkoutType.ROWING_MACHINE),
    (58, "Stretching", WorkoutType.STRETCHING),
    
    # Running & Combat (59-64)
    (59, "Track and field", WorkoutType.RUNNING),
    (60, "Orienteering", WorkoutType.ORIENTEERING),
    (61, "Standup paddling", WorkoutType.STAND_UP_PADDLEBOARDING),
    (62, "Combat sport", WorkoutType.MARTIAL_ARTS),
    (63, "Kettlebell", WorkoutType.STRENGTH_TRAINING),
    (64, "Dancing", WorkoutType.DANCE),
    
    # Additional Activities (65-87)
    (65, "Snow shoeing", WorkoutType.SNOWSHOEING),
    (66, "Frisbee golf", WorkoutType.OTHER),
    (67, "Futsal", WorkoutType.SOCCER),
    (68, "Multisport", WorkoutType.MULTISPORT),
    (69, "Aerobics", WorkoutType.AEROBICS),
    (70, "Trekking", WorkoutType.HIKING),
    (71, "Sailing", WorkoutType.SAILING),
    (72, "Kayaking", WorkoutType.KAYAKING),
    (73, "Circuit training", WorkoutType.STRENGTH_TRAINING),
    (74, "Triathlon", WorkoutType.TRIATHLON),
    (75, "Padel", WorkoutType.PADEL),
    (76, "Cheerleading", WorkoutType.AEROBICS),
    (77, "Boxing", WorkoutType.BOXING),
    (78, "Scubadiving", WorkoutType.DIVING),
    (79, "Freediving", WorkoutType.DIVING),
    (80, "Adventure racing", WorkoutType.MULTISPORT),
    (81, "Gymnastics", WorkoutType.FITNESS_EQUIPMENT),
    (82, "Canoeing", WorkoutType.CANOEING),
    (83, "Mountaineering", WorkoutType.MOUNTAINEERING),
    (84, "Telemarkskiing", WorkoutType.ALPINE_SKIING),
    (85, "Openwater swimming", WorkoutType.OPEN_WATER_SWIMMING),
    (86, "Windsurfing", WorkoutType.WINDSURFING),
    (87, "Kitesurfing", WorkoutType.KITESURFING),
    
    # Extended Activities (88-121)
    (88, "Paragliding", WorkoutType.OTHER),
    (90, "Snorkeling", WorkoutType.DIVING),
    (91, "Surfing", WorkoutType.SURFING),
    (92, "Swimrun", WorkoutType.MULTISPORT),
    (93, "Duathlon", WorkoutType.MULTISPORT),
    (94, "Aquathlon", WorkoutType.MULTISPORT),
    (95, "Obstacle racing", WorkoutType.RUNNING),
    (96, "Fishing", WorkoutType.OTHER),
    (97, "Hunting", WorkoutType.OTHER),
    (98, "Transition", WorkoutType.TRANSITION),
    (99, "Gravel cycling", WorkoutType.CYCLING),
    (100, "Mermaiding", WorkoutType.SWIMMING),
    (101, "Spearfishing", WorkoutType.DIVING),
    (102, "Jump rope", WorkoutType.CARDIO_TRAINING),
    (103, "Track running", WorkoutType.RUNNING),
    (104, "Calisthenics", WorkoutType.STRENGTH_TRAINING),
    (105, "E-biking", WorkoutType.E_BIKING),
    (106, "E-mtb", WorkoutType.E_BIKING),
    (107, "Backcountry skiing", WorkoutType.BACKCOUNTRY_SKIING),
    (108, "Wheelchair sport", WorkoutType.OTHER),
    (109, "Hand cycling", WorkoutType.CYCLING),
    (110, "Splitboarding", WorkoutType.SNOWBOARDING),
    (111, "Biathlon", WorkoutType.MULTISPORT),
    (112, "Meditation", WorkoutType.STRETCHING),
    (113, "Field hockey", WorkoutType.HOCKEY),
    (114, "Cyclocross", WorkoutType.CYCLOCROSS),
    (115, "Vertical running", WorkoutType.TRAIL_RUNNING),
    (116, "Ski mountaineering", WorkoutType.MOUNTAINEERING),
    (117, "Skate skiing", WorkoutType.CROSS_COUNTRY_SKIING),
    (118, "Classic skiing", WorkoutType.CROSS_COUNTRY_SKIING),
    (119, "Chores", WorkoutType.OTHER),
    (120, "Pilates", WorkoutType.PILATES),
    (121, "Yoga", WorkoutType.YOGA),
]

# Create lookup dictionaries
SUUNTO_ID_TO_UNIFIED: dict[int, WorkoutType] = {
    activity_id: unified_type
    for activity_id, _, unified_type in SUUNTO_WORKOUT_TYPE_MAPPINGS
}

SUUNTO_ID_TO_NAME: dict[int, str] = {
    activity_id: name
    for activity_id, name, _ in SUUNTO_WORKOUT_TYPE_MAPPINGS
}


def get_unified_workout_type(suunto_activity_id: int) -> WorkoutType:
    """
    Convert Suunto activity ID to unified WorkoutType.
    
    Args:
        suunto_activity_id: Suunto integer activity ID (0-121+)
    
    Returns:
        Unified WorkoutType enum value
    
    Examples:
        >>> get_unified_workout_type(0)  # Walking
        WorkoutType.WALKING
        >>> get_unified_workout_type(1)  # Running
        WorkoutType.RUNNING
        >>> get_unified_workout_type(22)  # Trail running
        WorkoutType.TRAIL_RUNNING
    """
    return SUUNTO_ID_TO_UNIFIED.get(suunto_activity_id, WorkoutType.OTHER)


def get_activity_name(suunto_activity_id: int) -> str:
    """Get the Suunto activity name for a given ID."""
    return SUUNTO_ID_TO_NAME.get(suunto_activity_id, "Unknown")