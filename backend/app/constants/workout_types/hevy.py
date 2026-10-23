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


# Exercise titles of cardio machines and activities as Hevy names them ("Ski Erg",
# "Rowing Machine", "Treadmill", "Air Bike", ...). Matched whole-word like the title map.
# A Hevy "Cycling" exercise is logged in a gym app, so it is indoor (BikeErg, spin bike).
HEVY_CARDIO_EXERCISE_KEYWORDS: dict[str, WorkoutType] = {
    "run": WorkoutType.RUNNING,
    "running": WorkoutType.RUNNING,
    "treadmill": WorkoutType.RUNNING,
    "jogging": WorkoutType.RUNNING,
    "sprint": WorkoutType.RUNNING,
    "sprints": WorkoutType.RUNNING,
    "walk": WorkoutType.WALKING,
    "walking": WorkoutType.WALKING,
    "hiking": WorkoutType.HIKING,
    "rowing": WorkoutType.ROWING_MACHINE,
    "rower": WorkoutType.ROWING_MACHINE,
    "row": WorkoutType.ROWING_MACHINE,
    "cycling": WorkoutType.INDOOR_CYCLING,
    "bike": WorkoutType.INDOOR_CYCLING,
    "bikeerg": WorkoutType.INDOOR_CYCLING,
    "spinning": WorkoutType.INDOOR_CYCLING,
    "elliptical": WorkoutType.ELLIPTICAL,
    "swimming": WorkoutType.SWIMMING,
    "swim": WorkoutType.SWIMMING,
    "ski": WorkoutType.CARDIO_TRAINING,
    "skierg": WorkoutType.CARDIO_TRAINING,
    "erg": WorkoutType.CARDIO_TRAINING,
    "stair": WorkoutType.CARDIO_TRAINING,
    "stepper": WorkoutType.CARDIO_TRAINING,
    "climber": WorkoutType.CARDIO_TRAINING,
    "rope": WorkoutType.CARDIO_TRAINING,
}
# Strength moves whose names contain a cardio word ("Upright Row", "Bent Over Row").
_STRENGTH_ROW_QUALIFIERS = {
    "upright",
    "bent",
    "barbell",
    "dumbbell",
    "cable",
    "seated",
    "pendlay",
    "renegade",
    "inverted",
    "t",
}


def cardio_exercise_type(title: str | None) -> WorkoutType | None:
    """The cardio activity an exercise title names, or None for anything else."""
    if not title:
        return None
    words = _WORD_RE.findall(title.lower())
    word_set = set(words)
    # The machine wins over the generic "row"/"erg" words: "Rowing Machine", "Ski Erg".
    for keyword, workout_type in HEVY_CARDIO_EXERCISE_KEYWORDS.items():
        if keyword not in word_set:
            continue
        if keyword == "row" and word_set & _STRENGTH_ROW_QUALIFIERS:
            return None
        if keyword == "erg" and "ski" not in word_set and "bike" not in word_set:
            # A bare "erg" is a rowing erg in gym language.
            return WorkoutType.ROWING_MACHINE
        return workout_type
    return None
