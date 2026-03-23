from app.schemas.enums import WorkoutType

from app.constants.workout_types.fitbit import get_unified_workout_type


def test_running_maps_correctly() -> None:
    assert get_unified_workout_type(90009, "Run") == WorkoutType.RUNNING


def test_walking_maps_correctly() -> None:
    assert get_unified_workout_type(90013, "Walk") == WorkoutType.WALKING


def test_unknown_id_falls_back_to_name() -> None:
    assert get_unified_workout_type(99999, "Yoga") == WorkoutType.YOGA


def test_unknown_id_and_name_returns_other() -> None:
    assert get_unified_workout_type(99999, "Unknown Activity XYZ") == WorkoutType.OTHER


def test_none_name_with_unknown_id_returns_other() -> None:
    assert get_unified_workout_type(99999) == WorkoutType.OTHER


def test_name_fallback_is_case_insensitive() -> None:
    assert get_unified_workout_type(99999, "YOGA") == WorkoutType.YOGA


def test_name_fallback_strips_whitespace() -> None:
    assert get_unified_workout_type(99999, "  walking  ") == WorkoutType.WALKING


def test_cycling_id_maps_correctly() -> None:
    assert get_unified_workout_type(90001, "Bike") == WorkoutType.CYCLING


def test_swimming_id_maps_correctly() -> None:
    assert get_unified_workout_type(82, "Swim") == WorkoutType.SWIMMING
