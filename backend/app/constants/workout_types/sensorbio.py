import logging

from app.schemas.enums import WorkoutType

logger = logging.getLogger(__name__)

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
    # Log unknown names so novel SensorBio activity types are discoverable.
    raw_name = likely_name or activity_type
    if raw_name:
        logger.info(
            "SensorBio workout type mapped to OTHER — add to SENSORBIO_NAME_TO_WORKOUT_TYPE if recurring",
            extra={"provider": "sensorbio", "raw_name": raw_name},
        )
    return WorkoutType.OTHER
