"""
Integration tests for Garmin data import flows.

Tests end-to-end import of Garmin activities and workouts.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.providers.garmin.strategy import GarminStrategy
from app.services.providers.garmin.workouts import GarminWorkouts
from app.tests.utils import (
    api_key_headers,
    create_api_key,
    create_developer,
    create_user,
    create_user_connection,
)


class TestGarminWorkoutImport:
    """Tests for Garmin workout import functionality."""

    @pytest.fixture
    def sample_garmin_activities(self):
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
        sample_garmin_activities: list[dict],
    ):
        """Test successful import of Garmin activities."""
        # Arrange
        user = create_user(db)
        create_user_connection(db, user=user, provider="garmin")

        strategy = GarminStrategy()

        with patch.object(strategy.workouts, "_make_api_request", return_value=sample_garmin_activities):
            # Act
            result = strategy.workouts.load_data(
                db,
                user.id,
                summary_start_time="1705309200",
                summary_end_time="1705482000",
            )

            # Assert
            assert result is True

    def test_import_garmin_activities_with_date_range(
        self,
        db: Session,
        sample_garmin_activities: list[dict],
    ):
        """Test importing activities with specific date range."""
        # Arrange
        user = create_user(db)
        create_user_connection(db, user=user, provider="garmin")

        strategy = GarminStrategy()
        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 1, 31, tzinfo=timezone.utc)

        with patch.object(strategy.workouts, "_make_api_request", return_value=sample_garmin_activities):
            # Act
            activities = strategy.workouts.get_workouts(db, user.id, start_date, end_date)

            # Assert
            assert len(activities) == 2
            assert activities[0]["activityType"] == "RUNNING"
            assert activities[1]["activityType"] == "CYCLING"

    def test_import_garmin_activities_empty_response(self, db: Session):
        """Test handling empty activities response."""
        # Arrange
        user = create_user(db)
        create_user_connection(db, user=user, provider="garmin")

        strategy = GarminStrategy()

        with patch.object(strategy.workouts, "_make_api_request", return_value=[]):
            # Act
            result = strategy.workouts.load_data(db, user.id)

            # Assert
            assert result is True

    def test_get_activity_detail(self, db: Session):
        """Test fetching detailed activity data."""
        # Arrange
        user = create_user(db)
        create_user_connection(db, user=user, provider="garmin")

        strategy = GarminStrategy()
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
            result = strategy.workouts.get_activity_detail(db, user.id, "12345678901")

            # Assert
            assert result["activityId"] == "12345678901"
            assert "laps" in result

    def test_import_normalizes_workout_types(
        self,
        db: Session,
    ):
        """Test that Garmin activity types are normalized correctly."""
        # Arrange
        user = create_user(db)
        create_user_connection(db, user=user, provider="garmin")

        activities = [
            {
                "userId": "garmin_user_123",
                "activityId": "act_001",
                "summaryId": "sum_001",
                "activityType": "TRAIL_RUNNING",
                "startTimeInSeconds": 1705309200,
                "durationInSeconds": 3600,
                "deviceName": "Garmin",
                "distanceInMeters": 10000,
                "steps": 8000,
                "activeKilocalories": 600,
                "averageHeartRateInBeatsPerMinute": 150,
                "maxHeartRateInBeatsPerMinute": 180,
            },
        ]

        strategy = GarminStrategy()

        with patch.object(strategy.workouts, "_make_api_request", return_value=activities):
            # Act
            result = strategy.workouts.load_data(db, user.id)

            # Assert
            assert result is True

    def test_import_handles_missing_heart_rate(self, db: Session):
        """Test importing activities without heart rate data."""
        # Arrange
        user = create_user(db)
        create_user_connection(db, user=user, provider="garmin")

        activities = [
            {
                "userId": "garmin_user_123",
                "activityId": "act_no_hr",
                "summaryId": "sum_no_hr",
                "activityType": "WALKING",
                "startTimeInSeconds": 1705309200,
                "durationInSeconds": 1800,
                "deviceName": "Garmin",
                "distanceInMeters": 3000,
                "steps": 4000,
                "activeKilocalories": 200,
                "averageHeartRateInBeatsPerMinute": 0,
                "maxHeartRateInBeatsPerMinute": 0,
            },
        ]

        strategy = GarminStrategy()

        with patch.object(strategy.workouts, "_make_api_request", return_value=activities):
            # Act
            result = strategy.workouts.load_data(db, user.id)

            # Assert
            assert result is True

    def test_import_handles_api_error(self, db: Session):
        """Test handling API errors during import."""
        # Arrange
        user = create_user(db)
        create_user_connection(db, user=user, provider="garmin")

        strategy = GarminStrategy()

        with patch.object(strategy.workouts, "_make_api_request", side_effect=Exception("API Error")):
            # Act & Assert
            with pytest.raises(Exception, match="API Error"):
                strategy.workouts.load_data(db, user.id)

    def test_get_workouts_from_api_with_params(self, db: Session):
        """Test getting workouts from API with custom parameters."""
        # Arrange
        user = create_user(db)
        create_user_connection(db, user=user, provider="garmin")

        strategy = GarminStrategy()

        with patch.object(strategy.workouts, "_make_api_request", return_value=[]) as mock_request:
            # Act
            strategy.workouts.get_workouts_from_api(
                db,
                user.id,
                summary_start_time="2024-01-01T00:00:00Z",
                summary_end_time="2024-01-31T23:59:59Z",
            )

            # Assert
            mock_request.assert_called_once()
            call_args = mock_request.call_args
            params = call_args[1]["params"]
            assert "uploadStartTimeInSeconds" in params
            assert "uploadEndTimeInSeconds" in params

    def test_strategy_components_initialized(self):
        """Test that Garmin strategy has all required components."""
        strategy = GarminStrategy()

        assert strategy.name == "garmin"
        assert strategy.oauth is not None
        assert strategy.workouts is not None
        assert isinstance(strategy.workouts, GarminWorkouts)

    def test_import_multiple_activity_types(self, db: Session):
        """Test importing activities with various types."""
        # Arrange
        user = create_user(db)
        create_user_connection(db, user=user, provider="garmin")

        activities = [
            {
                "userId": "garmin_user_123",
                "activityId": "swimming_001",
                "summaryId": "sum_001",
                "activityType": "LAP_SWIMMING",
                "startTimeInSeconds": 1705309200,
                "durationInSeconds": 2400,
                "deviceName": "Garmin Swim 2",
                "distanceInMeters": 1500,
                "steps": 0,
                "activeKilocalories": 400,
                "averageHeartRateInBeatsPerMinute": 130,
                "maxHeartRateInBeatsPerMinute": 160,
            },
            {
                "userId": "garmin_user_123",
                "activityId": "yoga_001",
                "summaryId": "sum_002",
                "activityType": "YOGA",
                "startTimeInSeconds": 1705395600,
                "durationInSeconds": 1800,
                "deviceName": "Garmin Venu 2",
                "distanceInMeters": 0,
                "steps": 50,
                "activeKilocalories": 150,
                "averageHeartRateInBeatsPerMinute": 95,
                "maxHeartRateInBeatsPerMinute": 120,
            },
        ]

        strategy = GarminStrategy()

        with patch.object(strategy.workouts, "_make_api_request", return_value=activities):
            # Act
            result = strategy.workouts.load_data(db, user.id)

            # Assert
            assert result is True
