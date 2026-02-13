"""
Integration tests for Garmin data import flows.

Tests end-to-end import of Garmin activities and workouts.
"""

from datetime import datetime, timezone
from typing import Any, cast
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.services.providers.garmin.strategy import GarminStrategy
from app.services.providers.garmin.workouts import GarminWorkouts
from tests.factories import UserConnectionFactory, UserFactory


class TestGarminWorkoutImport:
    """Tests for Garmin workout import functionality."""

    @pytest.fixture
    def sample_garmin_activities(self) -> list[dict[str, Any]]:
        """Sample Garmin activities API response."""
        return [
            {
                "userId": "garmin_user_123",
                "activityId": "12345678901",
                "summaryId": "summary_001",
                "activityType": "RUNNING",
                "startTimeInSeconds": 1705309200,
                "durationInSeconds": 3600,
                "deviceName": "Garmin Forerunner 945",
                "distanceInMeters": 10000,
                "steps": 8500,
                "activeKilocalories": 650,
                "averageHeartRateInBeatsPerMinute": 145,
                "maxHeartRateInBeatsPerMinute": 175,
            },
            {
                "userId": "garmin_user_123",
                "activityId": "12345678902",
                "summaryId": "summary_002",
                "activityType": "CYCLING",
                "startTimeInSeconds": 1705395600,
                "durationInSeconds": 5400,
                "deviceName": "Garmin Edge 830",
                "distanceInMeters": 35000,
                "steps": 0,
                "activeKilocalories": 850,
                "averageHeartRateInBeatsPerMinute": 135,
                "maxHeartRateInBeatsPerMinute": 165,
            },
        ]

    def test_load_data_is_noop(self, db: Session) -> None:
        """Test load_data is a no-op (data arrives via webhooks)."""
        user = UserFactory()
        UserConnectionFactory(user=user, provider="garmin")

        strategy = GarminStrategy()
        assert strategy.workouts is not None

        result = strategy.workouts.load_data(db, user.id)
        assert result is True

    def test_load_data_with_params_is_noop(self, db: Session) -> None:
        """Test load_data with date params is still a no-op."""
        user = UserFactory()
        UserConnectionFactory(user=user, provider="garmin")

        strategy = GarminStrategy()
        assert strategy.workouts is not None

        result = strategy.workouts.load_data(
            db,
            user.id,
            summary_start_time="1705309200",
            summary_end_time="1705482000",
        )
        assert result is True

    def test_import_garmin_activities_with_date_range(
        self,
        db: Session,
        sample_garmin_activities: list[dict[str, Any]],
    ) -> None:
        """Test importing activities with specific date range."""
        # Arrange
        user = UserFactory()
        UserConnectionFactory(user=user, provider="garmin")

        strategy = GarminStrategy()
        assert strategy.workouts is not None
        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 1, 31, tzinfo=timezone.utc)

        with patch.object(strategy.workouts, "_make_api_request", return_value=sample_garmin_activities):
            # Act
            activities = strategy.workouts.get_workouts(db, user.id, start_date, end_date)

            # Assert
            assert len(activities) == 2
            assert activities[0]["activityType"] == "RUNNING"
            assert activities[1]["activityType"] == "CYCLING"

    def test_get_activity_detail(self, db: Session) -> None:
        """Test fetching detailed activity data."""
        # Arrange
        user = UserFactory()
        UserConnectionFactory(user=user, provider="garmin")

        strategy = GarminStrategy()
        assert strategy.workouts is not None
        activity_detail = {
            "activityId": "12345678901",
            "summaryId": "summary_001",
            "userId": "garmin_user_123",
            "activityType": "RUNNING",
            "startTimeInSeconds": 1705309200,
            "durationInSeconds": 3600,
            "deviceName": "Garmin Forerunner 945",
            "distanceInMeters": 10000,
            "steps": 8500,
            "activeKilocalories": 650,
            "averageHeartRateInBeatsPerMinute": 145,
            "maxHeartRateInBeatsPerMinute": 175,
            "laps": [{"lapIndex": 1, "duration": 600}],
        }

        with patch.object(strategy.workouts, "_make_api_request", return_value=activity_detail):
            # Act
            result = cast(GarminWorkouts, strategy.workouts).get_activity_detail(db, user.id, "12345678901")

            # Assert
            assert result["activityId"] == "12345678901"
            assert "laps" in result

    def test_get_workouts_from_api_with_params(self, db: Session) -> None:
        """Test getting workouts from API with custom parameters.

        Note: For date ranges exceeding 24 hours, the implementation uses
        chunked fetching (24-hour chunks), so multiple API calls are made.
        """
        # Arrange
        user = UserFactory()
        UserConnectionFactory(user=user, provider="garmin")

        strategy = GarminStrategy()
        assert strategy.workouts is not None

        with patch.object(strategy.workouts, "_make_api_request", return_value=[]) as mock_request:
            # Act - using a 31-day date range
            strategy.workouts.get_workouts_from_api(
                db,
                user.id,
                summary_start_time="2024-01-01T00:00:00Z",
                summary_end_time="2024-01-31T23:59:59Z",
            )

            # Assert - multiple calls due to chunked fetching (24-hour chunks for 31 days)
            assert mock_request.call_count >= 1
            # Verify the API endpoint is correct
            first_call = mock_request.call_args_list[0]
            assert "/wellness-api/rest/activities" in first_call[0][2]
            # Verify params structure
            params = first_call[1]["params"]
            assert "uploadStartTimeInSeconds" in params
            assert "uploadEndTimeInSeconds" in params

    def test_strategy_components_initialized(self) -> None:
        """Test that Garmin strategy has all required components."""
        strategy = GarminStrategy()

        assert strategy.name == "garmin"
        assert strategy.oauth is not None
        assert strategy.workouts is not None
        assert isinstance(strategy.workouts, GarminWorkouts)
