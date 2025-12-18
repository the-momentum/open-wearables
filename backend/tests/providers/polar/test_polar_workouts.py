"""
Tests for Polar workouts implementation.

Tests the PolarWorkouts class for fetching and processing workout data from Polar API.
"""

from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.schemas import PolarExerciseJSON
from app.schemas.workout_types import WorkoutType
from app.services.providers.polar.workouts import PolarWorkouts
from tests.factories import UserConnectionFactory, UserFactory


class TestPolarWorkoutsInitialization:
    """Tests for PolarWorkouts initialization."""

    def test_polar_workouts_initialization(self, db: Session) -> None:
        """Test PolarWorkouts initializes with required dependencies."""
        # Arrange
        from app.models import EventRecord, User
        from app.repositories.event_record_repository import EventRecordRepository
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository
        from app.services.providers.polar.oauth import PolarOAuth

        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()
        workout_repo = EventRecordRepository(EventRecord)
        oauth = PolarOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
        )

        # Act
        workouts = PolarWorkouts(
            workout_repo=workout_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
            oauth=oauth,
        )

        # Assert
        assert workouts is not None
        assert workouts.provider_name == "polar"
        assert workouts.api_base_url == "https://www.polaraccesslink.com"
        assert workouts.oauth is oauth


class TestPolarWorkoutsDateExtraction:
    """Tests for Polar-specific date extraction with UTC offset."""

    def test_extract_dates_with_offset_positive_offset(self, db: Session) -> None:
        """Test extracting dates with positive UTC offset."""
        # Arrange
        from app.models import EventRecord, User
        from app.repositories.event_record_repository import EventRecordRepository
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository
        from app.services.providers.polar.oauth import PolarOAuth

        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()
        workout_repo = EventRecordRepository(EventRecord)
        oauth = PolarOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
        )
        workouts = PolarWorkouts(
            workout_repo=workout_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
            oauth=oauth,
        )

        # Act
        start_date, end_date = workouts._extract_dates_with_offset(
            start_time="2024-01-15T08:00:00",
            start_time_utc_offset=60,  # +1 hour
            duration="PT1H0M0S",  # 1 hour
        )

        # Assert
        assert isinstance(start_date, datetime)
        assert isinstance(end_date, datetime)
        assert end_date > start_date
        assert (end_date - start_date).total_seconds() == 3600  # 1 hour

    def test_extract_dates_with_offset_negative_offset(self, db: Session) -> None:
        """Test extracting dates with negative UTC offset."""
        # Arrange
        from app.models import EventRecord, User
        from app.repositories.event_record_repository import EventRecordRepository
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository
        from app.services.providers.polar.oauth import PolarOAuth

        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()
        workout_repo = EventRecordRepository(EventRecord)
        oauth = PolarOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
        )
        workouts = PolarWorkouts(
            workout_repo=workout_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
            oauth=oauth,
        )

        # Act
        start_date, end_date = workouts._extract_dates_with_offset(
            start_time="2024-01-15T08:00:00",
            start_time_utc_offset=-300,  # -5 hours
            duration="PT30M0S",  # 30 minutes
        )

        # Assert
        assert isinstance(start_date, datetime)
        assert isinstance(end_date, datetime)
        assert (end_date - start_date).total_seconds() == 1800  # 30 minutes

    def test_extract_dates_not_implemented_fallback(self, db: Session) -> None:
        """Test that _extract_dates raises NotImplementedError for Polar."""
        # Arrange
        from app.models import EventRecord, User
        from app.repositories.event_record_repository import EventRecordRepository
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository
        from app.services.providers.polar.oauth import PolarOAuth

        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()
        workout_repo = EventRecordRepository(EventRecord)
        oauth = PolarOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
        )
        workouts = PolarWorkouts(
            workout_repo=workout_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
            oauth=oauth,
        )

        # Act & Assert
        with pytest.raises(NotImplementedError):
            workouts._extract_dates("2024-01-15T08:00:00", "2024-01-15T09:00:00")


class TestPolarWorkoutsMetricsBuilding:
    """Tests for building metrics from Polar exercise data."""

    def test_build_metrics_with_heart_rate_data(self, db: Session, sample_polar_exercise: dict) -> None:
        """Test building metrics with complete heart rate data."""
        # Arrange
        from app.models import EventRecord, User
        from app.repositories.event_record_repository import EventRecordRepository
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository
        from app.services.providers.polar.oauth import PolarOAuth

        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()
        workout_repo = EventRecordRepository(EventRecord)
        oauth = PolarOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
        )
        workouts = PolarWorkouts(
            workout_repo=workout_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
            oauth=oauth,
        )

        exercise = PolarExerciseJSON(**sample_polar_exercise)

        # Act
        metrics = workouts._build_metrics(exercise)

        # Assert
        assert metrics["heart_rate_avg"] == Decimal("145")
        assert metrics["heart_rate_max"] == 175
        assert metrics["heart_rate_min"] == 145
        assert metrics["steps_total"] is None
        assert metrics["steps_avg"] is None

    def test_build_metrics_without_heart_rate_data(self, db: Session) -> None:
        """Test building metrics when heart rate data is missing."""
        # Arrange
        from app.models import EventRecord, User
        from app.repositories.event_record_repository import EventRecordRepository
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository
        from app.services.providers.polar.oauth import PolarOAuth

        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()
        workout_repo = EventRecordRepository(EventRecord)
        oauth = PolarOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
        )
        workouts = PolarWorkouts(
            workout_repo=workout_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
            oauth=oauth,
        )

        exercise = PolarExerciseJSON(
            id="ABC123",
            device="Polar Vantage V2",
            start_time="2024-01-15T08:00:00",
            start_time_utc_offset=60,
            duration="PT1H0M0S",
            sport="RUNNING",
            detailed_sport_info="RUNNING",
        )

        # Act
        metrics = workouts._build_metrics(exercise)

        # Assert
        assert metrics["heart_rate_avg"] is None
        assert metrics["heart_rate_max"] is None
        assert metrics["heart_rate_min"] is None


class TestPolarWorkoutsNormalization:
    """Tests for normalizing Polar exercises to event records."""

    def test_normalize_workout_complete_data(self, db: Session, sample_polar_exercise: dict) -> None:
        """Test normalizing workout with complete data."""
        # Arrange
        from app.models import EventRecord, User
        from app.repositories.event_record_repository import EventRecordRepository
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository
        from app.services.providers.polar.oauth import PolarOAuth

        user = UserFactory()
        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()
        workout_repo = EventRecordRepository(EventRecord)
        oauth = PolarOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
        )
        workouts = PolarWorkouts(
            workout_repo=workout_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
            oauth=oauth,
        )

        exercise = PolarExerciseJSON(**sample_polar_exercise)

        # Act
        record, detail = workouts._normalize_workout(exercise, user.id)

        # Assert
        assert record.category == "workout"
        assert record.type == WorkoutType.RUNNING.value
        assert record.source_name == "Polar Vantage V2"
        assert record.device_id == "Polar Vantage V2"
        assert record.duration_seconds == 3600
        assert record.provider_id == "ABC123"
        assert record.user_id == user.id
        assert detail.heart_rate_avg == Decimal("145")
        assert detail.heart_rate_max == 175

    def test_normalize_workout_workout_type_mapping(self, db: Session) -> None:
        """Test workout type is correctly mapped from Polar sport type."""
        # Arrange
        from app.models import EventRecord, User
        from app.repositories.event_record_repository import EventRecordRepository
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository
        from app.services.providers.polar.oauth import PolarOAuth

        user = UserFactory()
        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()
        workout_repo = EventRecordRepository(EventRecord)
        oauth = PolarOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
        )
        workouts = PolarWorkouts(
            workout_repo=workout_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
            oauth=oauth,
        )

        # Test cycling
        exercise = PolarExerciseJSON(
            id="CYC123",
            device="Polar Vantage V2",
            start_time="2024-01-15T08:00:00",
            start_time_utc_offset=60,
            duration="PT1H0M0S",
            sport="CYCLING",
            detailed_sport_info="CYCLING_ROAD",
        )

        # Act
        record, detail = workouts._normalize_workout(exercise, user.id)

        # Assert
        assert record.type == WorkoutType.CYCLING.value


class TestPolarWorkoutsAPIRequests:
    """Tests for API request methods."""

    @patch("app.services.providers.templates.base_workouts.make_authenticated_request")
    def test_get_workouts_from_api_default_params(self, mock_request: MagicMock, db: Session) -> None:
        """Test getting workouts with default parameters."""
        # Arrange
        from app.models import EventRecord, User
        from app.repositories.event_record_repository import EventRecordRepository
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository
        from app.services.providers.polar.oauth import PolarOAuth

        user = UserFactory()
        UserConnectionFactory(user=user, provider="polar")

        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()
        workout_repo = EventRecordRepository(EventRecord)
        oauth = PolarOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
        )
        workouts = PolarWorkouts(
            workout_repo=workout_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
            oauth=oauth,
        )

        mock_request.return_value = []

        # Act
        workouts.get_workouts_from_api(db, user.id)

        # Assert
        mock_request.assert_called_once()
        call_kwargs = mock_request.call_args[1]
        assert call_kwargs["endpoint"] == "/v3/exercises"
        assert call_kwargs["params"]["samples"] == "false"
        assert call_kwargs["params"]["zones"] == "false"
        assert call_kwargs["params"]["route"] == "false"

    @patch("app.services.providers.templates.base_workouts.make_authenticated_request")
    def test_get_workouts_from_api_with_options(self, mock_request: MagicMock, db: Session) -> None:
        """Test getting workouts with samples, zones, and route enabled."""
        # Arrange
        from app.models import EventRecord, User
        from app.repositories.event_record_repository import EventRecordRepository
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository
        from app.services.providers.polar.oauth import PolarOAuth

        user = UserFactory()
        UserConnectionFactory(user=user, provider="polar")

        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()
        workout_repo = EventRecordRepository(EventRecord)
        oauth = PolarOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
        )
        workouts = PolarWorkouts(
            workout_repo=workout_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
            oauth=oauth,
        )

        mock_request.return_value = []

        # Act
        workouts.get_workouts_from_api(db, user.id, samples=True, zones=True, route=True)

        # Assert
        mock_request.assert_called_once()
        call_kwargs = mock_request.call_args[1]
        assert call_kwargs["params"]["samples"] == "true"
        assert call_kwargs["params"]["zones"] == "true"
        assert call_kwargs["params"]["route"] == "true"

    @patch("app.services.providers.templates.base_workouts.make_authenticated_request")
    def test_get_workout_detail_from_api(self, mock_request: MagicMock, db: Session) -> None:
        """Test getting detailed workout data for specific exercise."""
        # Arrange
        from app.models import EventRecord, User
        from app.repositories.event_record_repository import EventRecordRepository
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository
        from app.services.providers.polar.oauth import PolarOAuth

        user = UserFactory()
        UserConnectionFactory(user=user, provider="polar")

        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()
        workout_repo = EventRecordRepository(EventRecord)
        oauth = PolarOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
        )
        workouts = PolarWorkouts(
            workout_repo=workout_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
            oauth=oauth,
        )

        mock_request.return_value = {}
        workout_id = "ABC123"

        # Act
        workouts.get_workout_detail_from_api(db, user.id, workout_id, samples=True)

        # Assert
        mock_request.assert_called_once()
        call_kwargs = mock_request.call_args[1]
        assert f"/v3/exercises/{workout_id}" in call_kwargs["endpoint"]
        assert call_kwargs["params"]["samples"] == "true"


class TestPolarWorkoutsDataLoading:
    """Tests for loading workout data from Polar API."""

    @patch("app.services.providers.templates.base_workouts.make_authenticated_request")
    @patch("app.services.event_record_service.event_record_service.create")
    @patch("app.services.event_record_service.event_record_service.create_detail")
    def test_load_data_success(
        self,
        mock_create_detail: MagicMock,
        mock_create: MagicMock,
        mock_request: MagicMock,
        db: Session,
        sample_polar_exercise: dict,
    ) -> None:
        """Test successful data loading from Polar API."""
        # Arrange
        from app.models import EventRecord, User
        from app.repositories.event_record_repository import EventRecordRepository
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository
        from app.services.providers.polar.oauth import PolarOAuth

        user = UserFactory()
        UserConnectionFactory(user=user, provider="polar")

        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()
        workout_repo = EventRecordRepository(EventRecord)
        oauth = PolarOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
        )
        workouts = PolarWorkouts(
            workout_repo=workout_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
            oauth=oauth,
        )

        mock_request.return_value = [sample_polar_exercise]

        # Act
        result = workouts.load_data(db, user.id)

        # Assert
        assert result is True
        mock_create.assert_called_once()
        mock_create_detail.assert_called_once()

    @patch("app.services.providers.templates.base_workouts.make_authenticated_request")
    def test_load_data_empty_response(self, mock_request: MagicMock, db: Session) -> None:
        """Test loading data when API returns empty list."""
        # Arrange
        from app.models import EventRecord, User
        from app.repositories.event_record_repository import EventRecordRepository
        from app.repositories.user_connection_repository import UserConnectionRepository
        from app.repositories.user_repository import UserRepository
        from app.services.providers.polar.oauth import PolarOAuth

        user = UserFactory()
        UserConnectionFactory(user=user, provider="polar")

        user_repo = UserRepository(User)
        connection_repo = UserConnectionRepository()
        workout_repo = EventRecordRepository(EventRecord)
        oauth = PolarOAuth(
            user_repo=user_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
        )
        workouts = PolarWorkouts(
            workout_repo=workout_repo,
            connection_repo=connection_repo,
            provider_name="polar",
            api_base_url="https://www.polaraccesslink.com",
            oauth=oauth,
        )

        mock_request.return_value = []

        # Act
        result = workouts.load_data(db, user.id)

        # Assert
        assert result is True
