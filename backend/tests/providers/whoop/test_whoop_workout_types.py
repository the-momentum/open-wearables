from app.constants.workout_types.whoop import get_unified_workout_type
from app.schemas.enums import WorkoutType


def test_weightlifting_msk_maps_to_strength_training() -> None:
    assert get_unified_workout_type("weightlifting_msk") == WorkoutType.STRENGTH_TRAINING


def test_foam_rolling_maps_to_recovery() -> None:
    assert get_unified_workout_type("foam_rolling") == WorkoutType.RECOVERY
