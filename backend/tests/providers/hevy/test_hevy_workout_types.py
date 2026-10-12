"""Tests for Hevy workout title -> unified WorkoutType mapping."""

from app.constants.workout_types.hevy import get_unified_workout_type
from app.schemas.enums import WorkoutType


class TestHevyWorkoutTypes:
    def test_default_is_strength_training(self) -> None:
        assert get_unified_workout_type("Push Day") == WorkoutType.STRENGTH_TRAINING
        assert get_unified_workout_type("Morning Workout") == WorkoutType.STRENGTH_TRAINING
        assert get_unified_workout_type(None) == WorkoutType.STRENGTH_TRAINING
        assert get_unified_workout_type("") == WorkoutType.STRENGTH_TRAINING

    def test_keyword_match(self) -> None:
        assert get_unified_workout_type("Easy Run") == WorkoutType.RUNNING
        assert get_unified_workout_type("Yoga session") == WorkoutType.YOGA
        assert get_unified_workout_type("bike commute") == WorkoutType.CYCLING

    def test_whole_word_only(self) -> None:
        # "running" inside another word must not match ("brunning" is not a run)
        assert get_unified_workout_type("Grunning grip work") == WorkoutType.STRENGTH_TRAINING

    def test_keyword_next_to_punctuation(self) -> None:
        assert get_unified_workout_type("Run: easy") == WorkoutType.RUNNING
        assert get_unified_workout_type("Easy run.") == WorkoutType.RUNNING
        assert get_unified_workout_type("(Yoga) flow") == WorkoutType.YOGA
        assert get_unified_workout_type("5k run") == WorkoutType.RUNNING
        assert get_unified_workout_type("bike/commute") == WorkoutType.CYCLING
        assert get_unified_workout_type("Trail-run") == WorkoutType.RUNNING

    def test_punctuation_does_not_split_words(self) -> None:
        # A keyword glued inside a longer word still does not count.
        assert get_unified_workout_type("Brunch: legs") == WorkoutType.STRENGTH_TRAINING
        assert get_unified_workout_type("Runway; push") == WorkoutType.STRENGTH_TRAINING
