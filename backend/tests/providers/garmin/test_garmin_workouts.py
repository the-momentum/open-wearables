"""Tests for Garmin workouts implementation."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models import EventRecord
from app.repositories.event_record_repository import EventRecordRepository
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas import EventRecordCreate, EventRecordDetailCreate, GarminActivityJSON
from app.schemas.workout_types import WorkoutType
from app.services.providers.garmin.oauth import GarminOAuth
from app.services.providers.garmin.workouts import GarminWorkouts
from tests.factories import UserConnectionFactory, UserFactory


class TestGarminWorkouts:
    """Tests for GarminWorkouts class."""

    @pytest.fixture
    def garmin_workouts(self, db: Session) -> GarminWorkouts:
        """Create GarminWorkouts instance for testing."""
        workout_repo = EventRecordRepository(EventRecord)
        connection_repo = UserConnectionRepository()
        oauth = GarminOAuth(
            user_repo=MagicMock(),
            connection_repo=connection_repo,
            provider_name="garmin",
            api_base_url="https://apis.garmin.com",
        )
        return GarminWorkouts(
            workout_repo=workout_repo,
            connection_repo=connection_repo,
            provider_name="garmin",
            api_base_url="https://apis.garmin.com",
            oauth=oauth,
        )

    @pytest.fixture
    def sample_activity(self) -> dict[str, Any]:
        """Sample Garmin activity data."""
        return {
            "userId": "garmin_user_123",
            "activityId": "12345678901",
            "summaryId": "summary_123",
            "activityType": "RUNNING",
            "startTimeInSeconds": 1705309200,  # 2024-01-15 08:00:00
            "durationInSeconds": 3600,
            "deviceName": "Garmin Forerunner 945",
            "distanceInMeters": 10000,
            "steps": 8500,
            "activeKilocalories": 650,
            "averageHeartRateInBeatsPerMinute": 145,
            "maxHeartRateInBeatsPerMinute": 175,
        }

    def test_get_workouts_builds_correct_params(self, garmin_workouts: GarminWorkouts, db: Session) -> None:
        """Test get_workouts builds correct API parameters."""
        # Arrange
        user = UserFactory()
        UserConnectionFactory(user=user, provider="garmin")

        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 1, 31, tzinfo=timezone.utc)

        with patch.object(garmin_workouts, "_make_api_request", return_value=[]) as mock_request:
            # Act
            garmin_workouts.get_workouts(db, user.id, start_date, end_date)

            # Assert
            mock_request.assert_called_once()
            call_args = mock_request.call_args
            params = call_args[1]["params"]
            assert params["uploadStartTimeInSeconds"] == int(start_date.timestamp())
            assert params["uploadEndTimeInSeconds"] == int(end_date.timestamp())

    def test_parse_timestamp_unix_format(self, garmin_workouts: GarminWorkouts) -> None:
        """Test parsing Unix timestamp."""
        result = garmin_workouts._parse_timestamp("1705309200")
        assert result == 1705309200

    def test_parse_timestamp_iso8601_format(self, garmin_workouts: GarminWorkouts) -> None:
        """Test parsing ISO 8601 date format."""
        result = garmin_workouts._parse_timestamp("2024-01-15T08:00:00Z")
        assert result is not None
        assert isinstance(result, int)

    def test_parse_timestamp_invalid_format(self, garmin_workouts: GarminWorkouts) -> None:
        """Test parsing invalid timestamp returns None."""
        result = garmin_workouts._parse_timestamp("invalid_timestamp")
        assert result is None

    def test_parse_timestamp_none_value(self, garmin_workouts: GarminWorkouts) -> None:
        """Test parsing None timestamp returns None."""
        result = garmin_workouts._parse_timestamp(None)
        assert result is None

    def test_extract_dates(self, garmin_workouts: GarminWorkouts) -> None:
        """Test extracting dates from timestamps."""
        start_ts = 1705309200  # 2024-01-15 08:00:00
        end_ts = 1705312800  # 2024-01-15 09:00:00

        start_date, end_date = garmin_workouts._extract_dates(start_ts, end_ts)

        assert isinstance(start_date, datetime)
        assert isinstance(end_date, datetime)
        assert start_date.timestamp() == start_ts
        assert end_date.timestamp() == end_ts

    def test_build_metrics_with_all_values(
        self,
        garmin_workouts: GarminWorkouts,
        sample_activity: dict[str, Any],
    ) -> None:
        """Test building metrics with all values present."""
        activity = GarminActivityJSON(**sample_activity)
        metrics = garmin_workouts._build_metrics(activity)

        assert metrics["heart_rate_avg"] == Decimal("145")
        assert metrics["heart_rate_max"] == 175
        assert metrics["heart_rate_min"] == 145
        assert metrics["steps_count"] == 8500

    def test_build_metrics_with_missing_values(self, garmin_workouts: GarminWorkouts) -> None:
        """Test building metrics with missing values."""
        activity = GarminActivityJSON(
            userId="user_123",
            activityId="act_123",
            summaryId="sum_123",
            activityType="RUNNING",
            startTimeInSeconds=1705309200,
            durationInSeconds=3600,
            deviceName="Garmin Device",
            distanceInMeters=10000,
            steps=0,
            activeKilocalories=0,
            averageHeartRateInBeatsPerMinute=0,
            maxHeartRateInBeatsPerMinute=0,
        )
        metrics = garmin_workouts._build_metrics(activity)

        # Should handle zero values
        assert metrics["steps_count"] == 0

    def test_normalize_workout(self, garmin_workouts: GarminWorkouts, sample_activity: dict[str, Any]) -> None:
        """Test normalizing Garmin activity to event record."""
        user_id = uuid4()
        activity = GarminActivityJSON(**sample_activity)

        record, detail = garmin_workouts._normalize_workout(activity, user_id)

        assert isinstance(record, EventRecordCreate)
        assert isinstance(detail, EventRecordDetailCreate)
        assert record.category == "workout"
        assert record.type == WorkoutType.RUNNING.value
        assert record.source_name == "Garmin Forerunner 945"
        assert record.device_id == "Garmin Forerunner 945"
        assert record.duration_seconds == 3600
        assert record.external_id == "12345678901"
        assert record.user_id == user_id

    def test_normalize_workout_with_different_types(self, garmin_workouts: GarminWorkouts) -> None:
        """Test normalizing different workout types."""
        user_id = uuid4()

        test_cases = [
            ("RUNNING", WorkoutType.RUNNING),
            ("CYCLING", WorkoutType.CYCLING),
            ("SWIMMING", WorkoutType.SWIMMING),
            ("TRAIL_RUNNING", WorkoutType.TRAIL_RUNNING),
            ("INDOOR_CYCLING", WorkoutType.INDOOR_CYCLING),
        ]

        for garmin_type, expected_type in test_cases:
            activity = GarminActivityJSON(
                userId="user_123",
                activityId=f"act_{garmin_type}",
                summaryId="sum_123",
                activityType=garmin_type,
                startTimeInSeconds=1705309200,
                durationInSeconds=3600,
                deviceName="Garmin Device",
                distanceInMeters=10000,
                steps=1000,
                activeKilocalories=500,
                averageHeartRateInBeatsPerMinute=140,
                maxHeartRateInBeatsPerMinute=170,
            )
            record, detail = garmin_workouts._normalize_workout(activity, user_id)
            assert record.type == expected_type.value

    def test_build_bundles(self, garmin_workouts: GarminWorkouts, sample_activity: dict[str, Any]) -> None:
        """Test building bundles from multiple activities."""
        user_id = uuid4()
        activity1 = GarminActivityJSON(**sample_activity)
        activity2 = GarminActivityJSON(
            userId=sample_activity["userId"],
            activityId="different_id",
            summaryId=sample_activity["summaryId"],
            activityType=sample_activity["activityType"],
            startTimeInSeconds=sample_activity["startTimeInSeconds"],
            durationInSeconds=sample_activity["durationInSeconds"],
            deviceName=sample_activity["deviceName"],
            distanceInMeters=sample_activity["distanceInMeters"],
            steps=sample_activity["steps"],
            activeKilocalories=sample_activity["activeKilocalories"],
            averageHeartRateInBeatsPerMinute=sample_activity["averageHeartRateInBeatsPerMinute"],
            maxHeartRateInBeatsPerMinute=sample_activity["maxHeartRateInBeatsPerMinute"],
        )
        activities = [activity1, activity2]

        bundles = list(garmin_workouts._build_bundles(activities, user_id))

        assert len(bundles) == 2
        for record, detail in bundles:
            assert isinstance(record, EventRecordCreate)
            assert isinstance(detail, EventRecordDetailCreate)

    def test_load_data_triggers_backfill(
        self,
        garmin_workouts: GarminWorkouts,
        db: Session,
        sample_activity: dict[str, Any],
    ) -> None:
        """Test load_data triggers backfill for activities."""
        user = UserFactory()

        with patch("app.services.providers.garmin.backfill.GarminBackfillService.trigger_backfill") as mock_trigger:
            mock_trigger.return_value = {
                "triggered": ["activities"],
                "failed": {},
                "start_time": "2024-01-14T00:00:00+00:00",
                "end_time": "2024-01-15T00:00:00+00:00",
            }

            result = garmin_workouts.load_data(db, user.id)

            assert result is True
            mock_trigger.assert_called_once()
            call_kwargs = mock_trigger.call_args[1]
            assert call_kwargs["data_types"] == ["activities"]

    def test_get_activity_detail(self, garmin_workouts: GarminWorkouts, db: Session) -> None:
        """Test getting activity detail from API."""
        user = UserFactory()
        UserConnectionFactory(user=user, provider="garmin")

        activity_detail = {"activityId": "123", "detailed": "data"}

        with patch.object(garmin_workouts, "_make_api_request", return_value=activity_detail) as mock_request:
            result = garmin_workouts.get_activity_detail(db, user.id, "123")

            assert result == activity_detail
            mock_request.assert_called_once_with(db, user.id, "/wellness-api/rest/activities/123")

    def test_get_workout_detail_from_api(self, garmin_workouts: GarminWorkouts, db: Session) -> None:
        """Test getting workout detail via public API method."""
        user = UserFactory()

        with patch.object(garmin_workouts, "get_activity_detail", return_value={"detail": "data"}) as mock_detail:
            result = garmin_workouts.get_workout_detail_from_api(db, user.id, "workout_123")

            assert result == {"detail": "data"}
            mock_detail.assert_called_once_with(db, user.id, "workout_123")
