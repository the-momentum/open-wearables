"""
Tests for SuuntoWorkouts.

Tests cover:
- Workout fetching from API
- Workout normalization
- Date extraction from timestamps
- Metrics building
- Workout detail fetching
- Subscription key header handling
- Data loading
- Workout type mapping
"""

from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, PropertyMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models import EventRecord
from app.repositories.event_record_repository import EventRecordRepository
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas import SuuntoWorkoutJSON
from app.schemas.workout_types import WorkoutType
from app.services.providers.suunto.oauth import SuuntoOAuth
from app.services.providers.suunto.workouts import SuuntoWorkouts


class TestSuuntoWorkouts:
    """Test suite for SuuntoWorkouts."""

    @pytest.fixture
    def suunto_workouts(self) -> SuuntoWorkouts:
        """Create SuuntoWorkouts instance for testing."""
        workout_repo = EventRecordRepository(EventRecord)
        connection_repo = UserConnectionRepository()
        oauth = SuuntoOAuth(
            user_repo=MagicMock(),
            connection_repo=connection_repo,
            provider_name="suunto",
            api_base_url="https://cloudapi.suunto.com",
        )
        return SuuntoWorkouts(
            workout_repo=workout_repo,
            connection_repo=connection_repo,
            provider_name="suunto",
            api_base_url="https://cloudapi.suunto.com",
            oauth=oauth,
        )

    @pytest.fixture
    def sample_workout_data(self) -> dict:
        """Sample Suunto workout data for testing."""
        return {
            "workoutId": 123456789,
            "activityId": 1,  # Running
            "startTime": 1705309200000,  # 2024-01-15T08:00:00 in milliseconds
            "stopTime": 1705312800000,  # 2024-01-15T09:00:00 in milliseconds
            "totalTime": 3600.0,  # 1 hour in seconds
            "totalDistance": 10000,
            "stepCount": 8500,
            "energyConsumption": 650,
            "hrdata": {
                "workoutMaxHR": 175,
                "workoutAvgHR": 145,
                "userMaxHR": 190,
                "avg": 145,
                "hrmax": 190,
                "max": 175,
            },
            "gear": {
                "manufacturer": "Suunto",
                "name": "Suunto 9 Peak",
                "displayName": "Suunto 9 Peak",
                "serialNumber": "SN123456",
            },
        }

    def test_extract_dates_from_millisecond_timestamps(self, suunto_workouts: SuuntoWorkouts) -> None:
        """Should extract datetime objects from millisecond timestamps."""
        # Arrange
        start_ms = 1705309200000  # 2024-01-15T08:00:00
        end_ms = 1705312800000  # 2024-01-15T09:00:00

        # Act
        start_date, end_date = suunto_workouts._extract_dates(start_ms, end_ms)

        # Assert
        assert isinstance(start_date, datetime)
        assert isinstance(end_date, datetime)
        assert start_date.year == 2024
        assert start_date.month == 1
        assert start_date.day == 15
        assert end_date > start_date

    def test_build_metrics_with_complete_data(
        self,
        suunto_workouts: SuuntoWorkouts,
        sample_workout_data: dict,
    ) -> None:
        """Should build metrics from complete workout data."""
        # Arrange
        workout = SuuntoWorkoutJSON(**sample_workout_data)

        # Act
        metrics = suunto_workouts._build_metrics(workout)

        # Assert
        assert metrics["heart_rate_avg"] == Decimal("145")
        assert metrics["heart_rate_max"] == 175
        assert metrics["heart_rate_min"] == 145
        assert metrics["steps_total"] == 8500
        assert metrics["steps_avg"] == Decimal("8500")

    def test_build_metrics_with_missing_heart_rate(
        self,
        suunto_workouts: SuuntoWorkouts,
        sample_workout_data: dict,
    ) -> None:
        """Should handle missing heart rate data."""
        # Arrange - use MagicMock to simulate a workout with None hrdata values
        mock_workout = MagicMock()
        mock_workout.hrdata = None
        mock_workout.stepCount = 8500

        # Act
        metrics = suunto_workouts._build_metrics(mock_workout)

        # Assert
        assert metrics["heart_rate_avg"] is None
        assert metrics["heart_rate_max"] is None
        assert metrics["heart_rate_min"] is None

    def test_build_metrics_with_missing_steps(
        self,
        suunto_workouts: SuuntoWorkouts,
        sample_workout_data: dict,
    ) -> None:
        """Should handle missing step count."""
        # Arrange - use MagicMock to simulate a workout with None stepCount
        mock_workout = MagicMock()
        mock_workout.hrdata.avg = 145
        mock_workout.hrdata.max = 175
        mock_workout.stepCount = None

        # Act
        metrics = suunto_workouts._build_metrics(mock_workout)

        # Assert
        assert metrics["steps_total"] is None
        assert metrics["steps_avg"] is None
        assert metrics["steps_min"] is None
        assert metrics["steps_max"] is None

    def test_normalize_workout_creates_event_record(
        self,
        suunto_workouts: SuuntoWorkouts,
        sample_workout_data: dict,
    ) -> None:
        """Should normalize Suunto workout to EventRecordCreate."""
        # Arrange
        workout = SuuntoWorkoutJSON(**sample_workout_data)
        user_id = uuid4()

        # Act
        record, detail = suunto_workouts._normalize_workout(workout, user_id)

        # Assert
        assert record.category == "workout"
        assert record.type == WorkoutType.RUNNING.value
        assert record.source_name == "Suunto 9 Peak"
        assert record.device_id == "SN123456"
        assert record.duration_seconds == 3600
        assert record.provider_id == "123456789"
        assert record.user_id == user_id

    def test_normalize_workout_without_device(self, suunto_workouts: SuuntoWorkouts, sample_workout_data: dict) -> None:
        """Should handle workout without device/gear information."""
        # Arrange
        sample_workout_data["gear"] = None
        workout = SuuntoWorkoutJSON(**sample_workout_data)
        user_id = uuid4()

        # Act
        record, detail = suunto_workouts._normalize_workout(workout, user_id)

        # Assert
        assert record.source_name == "Unknown"
        assert record.device_id is None

    def test_normalize_workout_creates_detail_with_metrics(
        self,
        suunto_workouts: SuuntoWorkouts,
        sample_workout_data: dict,
    ) -> None:
        """Should create workout detail with metrics."""
        # Arrange
        workout = SuuntoWorkoutJSON(**sample_workout_data)
        user_id = uuid4()

        # Act
        record, detail = suunto_workouts._normalize_workout(workout, user_id)

        # Assert
        assert detail.record_id == record.id
        assert detail.heart_rate_avg == Decimal("145")
        assert detail.heart_rate_max == 175
        assert detail.steps_total == 8500

    def test_get_suunto_headers_with_subscription_key(self, suunto_workouts: SuuntoWorkouts) -> None:
        """Should include subscription key in headers when available."""
        # Arrange
        # Mock credentials property using PropertyMock
        mock_creds = MagicMock()
        mock_creds.subscription_key = "test_subscription_key"
        with patch.object(type(suunto_workouts.oauth), "credentials", new_callable=PropertyMock) as mock_prop:
            mock_prop.return_value = mock_creds

            # Act
            headers = suunto_workouts._get_suunto_headers()

            # Assert
            assert "Ocp-Apim-Subscription-Key" in headers
            assert headers["Ocp-Apim-Subscription-Key"] == "test_subscription_key"

    @patch.object(SuuntoWorkouts, "_make_api_request")
    def test_get_workouts_from_api(
        self,
        mock_request: MagicMock,
        suunto_workouts: SuuntoWorkouts,
        db: Session,
        sample_workout_data: dict,
    ) -> None:
        """Should fetch workouts from Suunto API with correct parameters."""
        # Arrange
        from app.tests.utils import create_user

        user = create_user(db)
        mock_request.return_value = {"payload": [sample_workout_data]}

        # Act
        result = suunto_workouts.get_workouts_from_api(
            db,
            user.id,
            since=1705309200,
            limit=50,
            offset=0,
        )

        # Assert
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        # endpoint is third positional argument (db, user_id, endpoint)
        assert call_args[0][2] == "/v3/workouts/"
        assert call_args[1]["params"]["since"] == 1705309200
        assert call_args[1]["params"]["limit"] == 50
        assert result["payload"] == [sample_workout_data]

    @patch.object(SuuntoWorkouts, "_make_api_request")
    def test_get_workouts_respects_max_limit(
        self,
        mock_request: MagicMock,
        suunto_workouts: SuuntoWorkouts,
        db: Session,
    ) -> None:
        """Should respect maximum limit of 100 workouts per request."""
        # Arrange
        from app.tests.utils import create_user

        user = create_user(db)
        mock_request.return_value = {"payload": []}

        # Act
        suunto_workouts.get_workouts_from_api(db, user.id, since=0, limit=150)

        # Assert
        call_args = mock_request.call_args
        assert call_args[1]["params"]["limit"] == 100  # Capped at 100

    @patch.object(SuuntoWorkouts, "_make_api_request")
    def test_get_workout_detail(self, mock_request: MagicMock, suunto_workouts: SuuntoWorkouts, db: Session) -> None:
        """Should fetch detailed workout data from API."""
        # Arrange
        from app.tests.utils import create_user

        user = create_user(db)
        workout_key = "suunto-workout-123"
        mock_request.return_value = {"workoutKey": workout_key, "data": "details"}

        # Act
        result = suunto_workouts.get_workout_detail(db, user.id, workout_key)

        # Assert
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        # endpoint is third positional argument (db, user_id, endpoint)
        assert call_args[0][2] == f"/v3/workouts/{workout_key}"
        assert result["workoutKey"] == workout_key

    @patch.object(SuuntoWorkouts, "_make_api_request")
    @patch("app.services.event_record_service.event_record_service.create")
    @patch("app.services.event_record_service.event_record_service.create_detail")
    def test_load_data_creates_records(
        self,
        mock_create_detail: MagicMock,
        mock_create: MagicMock,
        mock_request: MagicMock,
        suunto_workouts: SuuntoWorkouts,
        db: Session,
        sample_workout_data: dict,
    ) -> None:
        """Should load data and create event records."""
        # Arrange
        from app.tests.utils import create_user

        user = create_user(db)
        mock_request.return_value = {"payload": [sample_workout_data]}

        # Act
        result = suunto_workouts.load_data(db, user.id, since=0, limit=10)

        # Assert
        assert result is True
        mock_create.assert_called_once()
        mock_create_detail.assert_called_once()
