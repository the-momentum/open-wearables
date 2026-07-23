from app.schemas.enums import WorkoutType

# Aliases only — Sensor Bio's `likely_name` / parent workout name can surface
# either noun or gerund forms (e.g. "Run" vs "Running"). They map to the same
# unified WorkoutType; they are not distinct Sensor Bio activity entities.
SENSORBIO_NAME_TO_WORKOUT_TYPE: dict[str, WorkoutType] = {
    "run": WorkoutType.RUNNING,
    "running": WorkoutType.RUNNING,
    "jog": WorkoutType.RUNNING,
    "jogging": WorkoutType.RUNNING,
    "treadmill": WorkoutType.RUNNING,
    "walk": WorkoutType.WALKING,
    "walking": WorkoutType.WALKING,
    "hike": WorkoutType.HIKING,
    "hiking": WorkoutType.HIKING,
    "bike": WorkoutType.CYCLING,
    "cycling": WorkoutType.CYCLING,
    "ride": WorkoutType.CYCLING,
    "bike ride": WorkoutType.CYCLING,
    "indoor cycling": WorkoutType.INDOOR_CYCLING,
    "spinning": WorkoutType.INDOOR_CYCLING,
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
    "hiit": WorkoutType.OTHER,
    "cardio": WorkoutType.OTHER,
    "cross training": WorkoutType.OTHER,
}


def get_unified_workout_type(likely_name: str | None = None, activity_type: str | None = None) -> WorkoutType:
    for candidate in (likely_name, activity_type):
        if not candidate:
            continue
        normalized = candidate.lower().strip()
        if normalized in SENSORBIO_NAME_TO_WORKOUT_TYPE:
            return SENSORBIO_NAME_TO_WORKOUT_TYPE[normalized]
    return WorkoutType.OTHER
