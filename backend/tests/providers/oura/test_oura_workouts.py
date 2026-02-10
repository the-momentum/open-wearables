"""Tests for OuraWorkouts."""

from uuid import uuid4

import pytest

from app.constants.workout_types.oura import get_unified_workout_type
from app.schemas.oura.imports import OuraWorkoutJSON
from app.schemas.workout_types import WorkoutType
from app.services.providers.oura.strategy import OuraStrategy
from app.services.providers.oura.workouts import OuraWorkouts


class TestOuraWorkoutTypeMapping:
    """Test workout type mapping from Oura activity strings."""

    def test_running(self) -> None:
        assert get_unified_workout_type("running") == WorkoutType.RUNNING

    def test_cycling(self) -> None:
        assert get_unified_workout_type("cycling") == WorkoutType.CYCLING

    def test_swimming(self) -> None:
        assert get_unified_workout_type("swimming") == WorkoutType.SWIMMING

    def test_yoga(self) -> None:
        assert get_unified_workout_type("yoga") == WorkoutType.YOGA

    def test_strength_training(self) -> None:
        assert get_unified_workout_type("strength_training") == WorkoutType.STRENGTH_TRAINING

    def test_hiking(self) -> None:
        assert get_unified_workout_type("hiking") == WorkoutType.HIKING

    def test_unknown_returns_other(self) -> None:
        assert get_unified_workout_type("some_unknown_activity") == WorkoutType.OTHER

    def test_none_returns_other(self) -> None:
        assert get_unified_workout_type(None) == WorkoutType.OTHER

    def test_case_insensitive(self) -> None:
        assert get_unified_workout_type("RUNNING") == WorkoutType.RUNNING
        assert get_unified_workout_type("Running") == WorkoutType.RUNNING


class TestOuraWorkoutsNormalization:
    """Test workout normalization."""

    @pytest.fixture
    def workouts(self) -> OuraWorkouts:
        strategy = OuraStrategy()
        return strategy.workouts

    @pytest.fixture
    def sample_oura_workout(self) -> OuraWorkoutJSON:
        return OuraWorkoutJSON(
            id="oura-workout-abc123",
            activity="running",
            calories=350.5,
            day="2024-01-15",
            distance=5000.0,
            end_datetime="2024-01-15T09:00:00+00:00",
            intensity="moderate",
            start_datetime="2024-01-15T08:00:00+00:00",
        )

    def test_normalize_workout_creates_records(
        self, workouts: OuraWorkouts, sample_oura_workout: OuraWorkoutJSON
    ) -> None:
        user_id = uuid4()
        record, detail = workouts._normalize_workout(sample_oura_workout, user_id)

        assert record.category == "workout"
        assert record.type == WorkoutType.RUNNING.value
        assert record.source_name == "Oura"
        assert record.source == "oura"
        assert record.user_id == user_id
        assert record.external_id == "oura-workout-abc123"
        assert record.duration_seconds == 3600

    def test_normalize_workout_metrics(self, workouts: OuraWorkouts, sample_oura_workout: OuraWorkoutJSON) -> None:
        user_id = uuid4()
        record, detail = workouts._normalize_workout(sample_oura_workout, user_id)

        assert detail.energy_burned is not None
        assert float(detail.energy_burned) == pytest.approx(350.5)
        assert detail.distance is not None
        assert float(detail.distance) == pytest.approx(5000.0)

    def test_normalize_workout_no_activity(self, workouts: OuraWorkouts) -> None:
        workout = OuraWorkoutJSON(
            id="oura-workout-no-activity",
            start_datetime="2024-01-15T08:00:00+00:00",
            end_datetime="2024-01-15T08:30:00+00:00",
        )
        user_id = uuid4()
        record, detail = workouts._normalize_workout(workout, user_id)

        assert record.type == WorkoutType.OTHER.value
        assert record.duration_seconds == 1800

    def test_build_bundles(self, workouts: OuraWorkouts, sample_oura_workout: OuraWorkoutJSON) -> None:
        user_id = uuid4()
        bundles = list(workouts._build_bundles([sample_oura_workout], user_id))
        assert len(bundles) == 1

        record, detail = bundles[0]
        assert record.category == "workout"
        assert detail.record_id == record.id
