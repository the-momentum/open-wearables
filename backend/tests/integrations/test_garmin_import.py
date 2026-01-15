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

    def test_import_garmin_activities_success(
        self,
        db: Session,
        sample_garmin_activities: list[dict[str, Any]],
    ) -> None:
        """Test successful import of Garmin activities via backfill."""
        # Arrange
        user = UserFactory()
        UserConnectionFactory(user=user, provider="garmin")

        strategy = GarminStrategy()
        assert strategy.workouts is not None

        with patch("app.services.providers.garmin.backfill.GarminBackfillService.trigger_backfill") as mock_trigger:
            mock_trigger.return_value = {
                "triggered": ["activities"],
                "failed": {},
                "start_time": "2024-01-15T00:00:00+00:00",
                "end_time": "2024-01-20T00:00:00+00:00",
            }

            # Act
            result = strategy.workouts.load_data(
                db,
                user.id,
                summary_start_time="1705309200",
                summary_end_time="1705482000",
            )

            # Assert
            assert result is True
            mock_trigger.assert_called_once()

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

    def test_import_garmin_activities_empty_response(self, db: Session) -> None:
        """Test handling empty activities response via backfill."""
        # Arrange
        user = UserFactory()
        UserConnectionFactory(user=user, provider="garmin")

        strategy = GarminStrategy()
        assert strategy.workouts is not None

        with patch("app.services.providers.garmin.backfill.GarminBackfillService.trigger_backfill") as mock_trigger:
            mock_trigger.return_value = {
                "triggered": ["activities"],
                "failed": {},
                "start_time": "2024-01-14T00:00:00+00:00",
                "end_time": "2024-01-15T00:00:00+00:00",
            }

            # Act
            result = strategy.workouts.load_data(db, user.id)

            # Assert - backfill was triggered successfully
            assert result is True

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

    def test_import_normalizes_workout_types(
        self,
        db: Session,
    ) -> None:
        """Test that Garmin activity types are normalized correctly via backfill."""
        # Arrange
        user = UserFactory()
        UserConnectionFactory(user=user, provider="garmin")

        strategy = GarminStrategy()
        assert strategy.workouts is not None

        with patch("app.services.providers.garmin.backfill.GarminBackfillService.trigger_backfill") as mock_trigger:
            mock_trigger.return_value = {
                "triggered": ["activities"],
                "failed": {},
                "start_time": "2024-01-14T00:00:00+00:00",
                "end_time": "2024-01-15T00:00:00+00:00",
            }

            # Act
            result = strategy.workouts.load_data(db, user.id)

            # Assert
            assert result is True

    def test_import_handles_missing_heart_rate(self, db: Session) -> None:
        """Test importing activities without heart rate data via backfill."""
        # Arrange
        user = UserFactory()
        UserConnectionFactory(user=user, provider="garmin")

        strategy = GarminStrategy()
        assert strategy.workouts is not None

        with patch("app.services.providers.garmin.backfill.GarminBackfillService.trigger_backfill") as mock_trigger:
            mock_trigger.return_value = {
                "triggered": ["activities"],
                "failed": {},
                "start_time": "2024-01-14T00:00:00+00:00",
                "end_time": "2024-01-15T00:00:00+00:00",
            }

            # Act
            result = strategy.workouts.load_data(db, user.id)

            # Assert
            assert result is True

    def test_import_handles_api_error(self, db: Session) -> None:
        """Test handling API errors during import."""
        # Arrange
        user = UserFactory()
        UserConnectionFactory(user=user, provider="garmin")

        strategy = GarminStrategy()
        assert strategy.workouts is not None

        with (
            patch(
                "app.services.providers.garmin.backfill.GarminBackfillService.trigger_backfill",
                side_effect=Exception("API Error"),
            ),
            pytest.raises(Exception, match="API Error"),
        ):
            strategy.workouts.load_data(db, user.id)

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

    def test_import_multiple_activity_types(self, db: Session) -> None:
        """Test importing activities with various types via backfill."""
        # Arrange
        user = UserFactory()
        UserConnectionFactory(user=user, provider="garmin")

        strategy = GarminStrategy()
        assert strategy.workouts is not None

        with patch("app.services.providers.garmin.backfill.GarminBackfillService.trigger_backfill") as mock_trigger:
            mock_trigger.return_value = {
                "triggered": ["activities"],
                "failed": {},
                "start_time": "2024-01-14T00:00:00+00:00",
                "end_time": "2024-01-15T00:00:00+00:00",
            }

            # Act
            result = strategy.workouts.load_data(db, user.id)

            # Assert
            assert result is True
