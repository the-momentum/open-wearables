from app.schemas.workout_types import WorkoutType

# Fitbit activity type IDs → UnifiedWorkoutType
# Source: https://dev.fitbit.com/build/reference/web-api/activity/get-activity-type/
FITBIT_ID_TO_WORKOUT_TYPE: dict[int, WorkoutType] = {
    # Running
    90009: WorkoutType.RUNNING,
    2131: WorkoutType.RUNNING,  # Indoor Running on some Fitbit devices
    91: WorkoutType.TREADMILL,
    # Walking
    90013: WorkoutType.WALKING,
    # Cycling
    90001: WorkoutType.CYCLING,
    90024: WorkoutType.INDOOR_CYCLING,
    # Swimming
    82: WorkoutType.SWIMMING,
    # Strength / Gym
    3000: WorkoutType.STRENGTH_TRAINING,
    # Yoga
    52001: WorkoutType.YOGA,
    # Hiking
    1071: WorkoutType.HIKING,
    # Sports
    15: WorkoutType.SOCCER,
    16: WorkoutType.BASKETBALL,
    27: WorkoutType.TENNIS,
    # Other
    90019: WorkoutType.OTHER,
}

# Fallback: normalize Fitbit activityName → WorkoutType
FITBIT_NAME_TO_WORKOUT_TYPE: dict[str, WorkoutType] = {
    "run": WorkoutType.RUNNING,
    "running": WorkoutType.RUNNING,
    "treadmill": WorkoutType.TREADMILL,
    "walk": WorkoutType.WALKING,
    "walking": WorkoutType.WALKING,
    "bike": WorkoutType.CYCLING,
    "cycling": WorkoutType.CYCLING,
    "indoor cycling": WorkoutType.INDOOR_CYCLING,
    "swim": WorkoutType.SWIMMING,
    "swimming": WorkoutType.SWIMMING,
    "yoga": WorkoutType.YOGA,
    "pilates": WorkoutType.PILATES,
    "hike": WorkoutType.HIKING,
    "hiking": WorkoutType.HIKING,
    "strength training": WorkoutType.STRENGTH_TRAINING,
    "weights": WorkoutType.STRENGTH_TRAINING,
    "tennis": WorkoutType.TENNIS,
    "soccer": WorkoutType.SOCCER,
    "basketball": WorkoutType.BASKETBALL,
    "rowing": WorkoutType.ROWING,
    "elliptical": WorkoutType.ELLIPTICAL,
    "stair climbing": WorkoutType.STAIR_CLIMBING,
    "golf": WorkoutType.GOLF,
    "dance": WorkoutType.DANCE,
    "stretching": WorkoutType.STRETCHING,
}


def get_unified_workout_type(activity_type_id: int, activity_name: str | None = None) -> WorkoutType:
    """Convert Fitbit activity type to unified WorkoutType.

    Args:
        activity_type_id: Fitbit numeric activityTypeId
        activity_name: Fitbit activityName string (fallback)

    Returns:
        Unified WorkoutType enum value
    """
    if activity_type_id in FITBIT_ID_TO_WORKOUT_TYPE:
        return FITBIT_ID_TO_WORKOUT_TYPE[activity_type_id]

    if activity_name:
        normalized = activity_name.lower().strip()
        if normalized in FITBIT_NAME_TO_WORKOUT_TYPE:
            return FITBIT_NAME_TO_WORKOUT_TYPE[normalized]

    return WorkoutType.OTHER
