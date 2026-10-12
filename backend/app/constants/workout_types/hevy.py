import re

from app.schemas.enums import WorkoutType

# Runs of letters only: punctuation, digits and separators all split words, so
# "Run: easy" and "5k run" match "run" while "Grunning" stays one word.
_WORD_RE = re.compile(r"[^\W\d_]+")

# Hevy is a gym/strength tracker: workouts have no activity-type field, only a
# free-form title ("Morning Workout", "Push Day", ...). Everything defaults to
# STRENGTH_TRAINING; the keyword map below only catches titles that clearly
# describe a non-lifting session logged in Hevy.
HEVY_TITLE_KEYWORD_TO_WORKOUT_TYPE: dict[str, WorkoutType] = {
    "run": WorkoutType.RUNNING,
    "running": WorkoutType.RUNNING,
    "treadmill": WorkoutType.RUNNING,
    "walk": WorkoutType.WALKING,
    "walking": WorkoutType.WALKING,
    "hike": WorkoutType.HIKING,
    "hiking": WorkoutType.HIKING,
    "cycling": WorkoutType.CYCLING,
    "bike": WorkoutType.CYCLING,
    "spinning": WorkoutType.INDOOR_CYCLING,
    "swim": WorkoutType.SWIMMING,
    "swimming": WorkoutType.SWIMMING,
    "yoga": WorkoutType.YOGA,
    "pilates": WorkoutType.PILATES,
    "rowing": WorkoutType.ROWING,
    "stretching": WorkoutType.OTHER,
    "cardio": WorkoutType.OTHER,
}


def get_unified_workout_type(title: str | None = None) -> WorkoutType:
    """Map a Hevy workout title to a unified WorkoutType.

    Whole-word keyword match on the title; defaults to STRENGTH_TRAINING
    (Hevy sessions are gym workouts unless the title says otherwise).
    """
    if title:
        words = set(_WORD_RE.findall(title.lower()))
        for keyword, workout_type in HEVY_TITLE_KEYWORD_TO_WORKOUT_TYPE.items():
            if keyword in words:
                return workout_type
    return WorkoutType.STRENGTH_TRAINING
