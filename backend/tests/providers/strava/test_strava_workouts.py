"""Tests for StravaWorkouts normalization."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.schemas.enums import EntrySource
from app.schemas.providers.strava import ActivityJSON as StravaActivityJSON
from app.services.providers.strava.oauth import StravaOAuth
from app.services.providers.strava.workouts import StravaWorkouts


class TestStravaWorkoutsNormalization:
    """Test workout normalization."""

    @pytest.fixture
    def workouts(self) -> StravaWorkouts:
        oauth = StravaOAuth(
            user_repo=MagicMock(),
            connection_repo=MagicMock(),
            provider_name="strava",
            api_base_url="https://www.strava.com/api/v3",
        )
        return StravaWorkouts(
            workout_repo=MagicMock(),
            connection_repo=MagicMock(),
            provider_name="strava",
            api_base_url="https://www.strava.com/api/v3",
            oauth=oauth,
        )

    def _activity(self, manual: bool | None = None) -> StravaActivityJSON:
        return StravaActivityJSON(
            id=12345,
            name="Evening Ride",
            type="Ride",
            sport_type="Ride",
            start_date="2024-01-15T18:00:00Z",
            elapsed_time=3600,
            manual=manual,
        )

    def test_normalize_workout_manual_entry(self, workouts: StravaWorkouts) -> None:
        record, detail = workouts._normalize_workout(self._activity(manual=True), uuid4())

        assert record.source == "strava"  # provider identifier, unrelated to entry_source
        assert detail.entry_source == EntrySource.MANUAL
        assert detail.label == "Evening Ride"

    def test_normalize_workout_auto_entry(self, workouts: StravaWorkouts) -> None:
        _, detail = workouts._normalize_workout(self._activity(manual=False), uuid4())

        assert detail.entry_source == EntrySource.AUTOMATIC

    def test_normalize_workout_unknown_entry_source(self, workouts: StravaWorkouts) -> None:
        _, detail = workouts._normalize_workout(self._activity(), uuid4())

        assert detail.entry_source is None
