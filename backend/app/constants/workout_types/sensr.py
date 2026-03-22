from app.schemas.workout_types import WorkoutType

SENSR_NAME_TO_WORKOUT_TYPE: dict[str, WorkoutType] = {
    "run": WorkoutType.RUNNING,
    "running": WorkoutType.RUNNING,
    "walk": WorkoutType.WALKING,
    "walking": WorkoutType.WALKING,
    "hike": WorkoutType.HIKING,
    "hiking": WorkoutType.HIKING,
    "bike": WorkoutType.CYCLING,
    "cycling": WorkoutType.CYCLING,
    "ride": WorkoutType.CYCLING,
    "indoor cycling": WorkoutType.INDOOR_CYCLING,
    "swim": WorkoutType.SWIMMING,
    "swimming": WorkoutType.SWIMMING,
    "strength": WorkoutType.STRENGTH_TRAINING,
    "strength training": WorkoutType.STRENGTH_TRAINING,
    "weights": WorkoutType.STRENGTH_TRAINING,
    "workout": WorkoutType.OTHER,
    "yoga": WorkoutType.YOGA,
    "pilates": WorkoutType.PILATES,
    "rowing": WorkoutType.ROWING,
    "elliptical": WorkoutType.ELLIPTICAL,
    "stair climbing": WorkoutType.STAIR_CLIMBING,
    "soccer": WorkoutType.SOCCER,
    "basketball": WorkoutType.BASKETBALL,
    "tennis": WorkoutType.TENNIS,
    "golf": WorkoutType.GOLF,
    "dance": WorkoutType.DANCE,
}


def get_unified_workout_type(likely_name: str | None = None, activity_type: str | None = None) -> WorkoutType:
    for candidate in (likely_name, activity_type):
        if not candidate:
            continue
        normalized = candidate.lower().strip()
        if normalized in SENSR_NAME_TO_WORKOUT_TYPE:
            return SENSR_NAME_TO_WORKOUT_TYPE[normalized]
    return WorkoutType.OTHER
