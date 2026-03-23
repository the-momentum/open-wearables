from app.constants.workout_types.sensorbio import get_unified_workout_type
from app.schemas.workout_types import WorkoutType


def test_sensorbio_workout_type_from_likely_name() -> None:
    assert get_unified_workout_type("running") == WorkoutType.RUNNING


def test_sensorbio_workout_type_from_type_fallback() -> None:
    assert get_unified_workout_type(None, "cycling") == WorkoutType.CYCLING


def test_sensorbio_workout_type_unknown_defaults_to_other() -> None:
    assert get_unified_workout_type("mystery sport") == WorkoutType.OTHER
