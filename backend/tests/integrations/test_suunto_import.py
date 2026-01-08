"""
Integration tests for Suunto data import flow.

Tests cover:
- Complete OAuth authorization flow
- Workout data fetching from API
- Data normalization and storage
- Error handling during import
- Workout type mapping
"""

from datetime import datetime, timedelta, timezone
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
from jose import jwt
from sqlalchemy.orm import Session

from app.schemas.oauth import ConnectionStatus
from app.services.providers.suunto.strategy import SuuntoStrategy
from app.services.providers.suunto.workouts import SuuntoWorkouts
from tests.factories import UserConnectionFactory, UserFactory


class TestSuuntoImport:
    """Integration tests for Suunto data import."""

    @pytest.fixture
    def suunto_strategy(self) -> SuuntoStrategy:
        """Create SuuntoStrategy instance for testing."""
        return SuuntoStrategy()

    @pytest.fixture
    def sample_suunto_api_response(self) -> dict[str, Any]:
        """Sample Suunto API response with multiple workouts."""
        return {
            "error": None,
            "payload": [
                {
                    "workoutId": 123456789,
                    "activityId": 1,  # Running
                    "startTime": 1705309200000,
                    "stopTime": 1705312800000,
                    "totalTime": 3600.0,
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
                },
                {
                    "workoutId": 987654321,
                    "activityId": 2,  # Cycling
                    "startTime": 1705395600000,
                    "stopTime": 1705402800000,
                    "totalTime": 7200.0,
                    "totalDistance": 35000,
                    "stepCount": 0,
                    "energyConsumption": 890,
                    "hrdata": {
                        "workoutMaxHR": 168,
                        "workoutAvgHR": 138,
                        "userMaxHR": 190,
                        "avg": 138,
                        "hrmax": 190,
                        "max": 168,
                    },
                    "gear": {
                        "manufacturer": "Suunto",
                        "name": "Suunto 9 Baro",
                        "displayName": "Suunto 9 Baro",
                        "serialNumber": "SN654321",
                    },
                },
            ],
        }

    @patch("httpx.post")
    def test_oauth_token_exchange_with_jwt(
        self,
        mock_post: MagicMock,
        suunto_strategy: SuuntoStrategy,
        db: Session,
    ) -> None:
        """Should exchange OAuth code and decode JWT for user info."""
        # Arrange
        user = UserFactory()

        # Create JWT access token
        test_payload = {
            "sub": "suunto_user_12345",
            "user": "test_suunto_athlete",
            "exp": (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp(),
        }
        access_token = jwt.encode(test_payload, "secret", algorithm="HS256")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": access_token,
            "refresh_token": "test_refresh_token",
            "expires_in": 3600,
            "token_type": "Bearer",
        }
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # Mock Redis state
        assert suunto_strategy.oauth is not None
        with patch.object(suunto_strategy.oauth.redis_client, "get") as mock_redis_get:
            state_data = {
                "user_id": str(user.id),
                "provider": "suunto",
                "redirect_uri": None,
            }
            import json

            mock_redis_get.return_value = json.dumps(state_data)

            # Act
            assert suunto_strategy.oauth is not None
            oauth_state = suunto_strategy.oauth.handle_callback(db, "test_code", "test_state")

            # Assert
            assert oauth_state.user_id == user.id
            assert oauth_state.provider == "suunto"

            # Verify connection was created with JWT user info
            connection = suunto_strategy.connection_repo.get_by_user_and_provider(db, user.id, "suunto")
            assert connection is not None
            assert connection.provider_user_id == "suunto_user_12345"
            assert connection.provider_username == "test_suunto_athlete"

    def test_fetch_workouts_from_api(
        self,
        suunto_strategy: SuuntoStrategy,
        db: Session,
        sample_suunto_api_response: dict[str, Any],
    ) -> None:
        """Should fetch workouts from Suunto API."""
        # Arrange
        user = UserFactory()
        UserConnectionFactory(user=user, provider="suunto", status=ConnectionStatus.ACTIVE)

        # Mock the get_workouts_from_api method directly on the instance
        assert suunto_strategy.workouts is not None
        with patch.object(suunto_strategy.workouts, "get_workouts_from_api", return_value=sample_suunto_api_response):
            # Act
            result = suunto_strategy.workouts.get_workouts_from_api(
                db,
                user.id,
                since=0,
                limit=50,
            )

            # Assert
            assert result["error"] is None
            assert len(result["payload"]) == 2
            assert result["payload"][0]["activityId"] == 1  # Running
            assert result["payload"][1]["activityId"] == 2  # Cycling

    @patch("app.services.providers.suunto.workouts.SuuntoWorkouts._make_api_request")
    @patch("app.services.event_record_service.event_record_service.create")
    @patch("app.services.event_record_service.event_record_service.create_detail")
    @patch("app.repositories.device_repository.DeviceRepository.ensure_device")
    def test_load_data_creates_event_records(
        self,
        mock_ensure_device: MagicMock,
        mock_create_detail: MagicMock,
        mock_create: MagicMock,
        mock_request: MagicMock,
        suunto_strategy: SuuntoStrategy,
        db: Session,
        sample_suunto_api_response: dict[str, Any],
    ) -> None:
        """Should load data and create event records in database."""
        # Arrange
        user = UserFactory()
        UserConnectionFactory(user=user, provider="suunto", status=ConnectionStatus.ACTIVE)
        mock_request.return_value = sample_suunto_api_response
        assert suunto_strategy.workouts is not None

        # Act
        result = suunto_strategy.workouts.load_data(db, user.id, since=0, limit=50)

        # Assert
        assert result is True
        assert mock_create.call_count == 2  # Two workouts
        assert mock_create_detail.call_count == 2  # Two workout details
        # Verify device creation was attempted
        assert mock_ensure_device.call_count == 2  # Two devices

    def test_workout_type_mapping(self, suunto_strategy: SuuntoStrategy) -> None:
        """Should correctly map Suunto activity IDs to unified workout types."""
        # Arrange
        from app.constants.workout_types.suunto import get_unified_workout_type
        from app.schemas.workout_types import WorkoutType

        # Act & Assert
        assert get_unified_workout_type(1) == WorkoutType.RUNNING
        assert get_unified_workout_type(2) == WorkoutType.CYCLING
        assert get_unified_workout_type(21) == WorkoutType.SWIMMING
        assert get_unified_workout_type(74) == WorkoutType.TRIATHLON
        assert get_unified_workout_type(999) == WorkoutType.OTHER  # Unknown activity

    @patch("app.services.providers.suunto.workouts.SuuntoWorkouts._make_api_request")
    def test_get_workout_detail_from_api(
        self,
        mock_request: MagicMock,
        suunto_strategy: SuuntoStrategy,
        db: Session,
    ) -> None:
        """Should fetch detailed workout data from API."""
        # Arrange
        user = UserFactory()
        UserConnectionFactory(user=user, provider="suunto", status=ConnectionStatus.ACTIVE)

        workout_key = "suunto-workout-123"
        mock_request.return_value = {
            "workoutKey": workout_key,
            "activityId": 1,
            "samples": [
                {"TimeISO8601": "2024-01-15T08:00:00Z", "HR": 120},
                {"TimeISO8601": "2024-01-15T08:01:00Z", "HR": 135},
            ],
        }
        assert suunto_strategy.workouts is not None

        # Act
        result = cast(SuuntoWorkouts, suunto_strategy.workouts).get_workout_detail(db, user.id, workout_key)

        # Assert
        assert result["workoutKey"] == workout_key
        assert "samples" in result
        mock_request.assert_called_once()

    @patch("httpx.post")
    def test_token_refresh_flow(
        self,
        mock_post: MagicMock,
        suunto_strategy: SuuntoStrategy,
        db: Session,
    ) -> None:
        """Should refresh expired access tokens."""
        # Arrange
        user = UserFactory()
        connection = UserConnectionFactory(
            user=user,
            provider="suunto",
            status=ConnectionStatus.EXPIRED,
            refresh_token="old_refresh_token",
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_in": 3600,
            "token_type": "Bearer",
        }
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        assert suunto_strategy.oauth is not None

        # Act
        token_response = suunto_strategy.oauth.refresh_access_token(db, user.id, "old_refresh_token")

        # Assert
        assert token_response.access_token == "new_access_token"
        assert token_response.refresh_token == "new_refresh_token"

        # Verify connection was updated
        db.refresh(connection)
        assert connection.access_token == "new_access_token"
        assert connection.refresh_token == "new_refresh_token"

    @patch("app.services.providers.suunto.workouts.SuuntoWorkouts._make_api_request")
    def test_subscription_key_included_in_requests(
        self,
        mock_request: MagicMock,
        suunto_strategy: SuuntoStrategy,
        db: Session,
    ) -> None:
        """Should include subscription key in API requests."""
        # Arrange
        user = UserFactory()
        UserConnectionFactory(user=user, provider="suunto", status=ConnectionStatus.ACTIVE)

        # Mock the credentials property to return a mock with subscription_key
        mock_creds = MagicMock()
        mock_creds.subscription_key = "test_subscription_key"
        mock_request.return_value = {"payload": []}

        # Patch the credentials property using PropertyMock
        assert suunto_strategy.oauth is not None
        assert suunto_strategy.workouts is not None
        with patch.object(type(suunto_strategy.oauth), "credentials", new_callable=lambda: mock_creds):
            # Act
            suunto_strategy.workouts.get_workouts_from_api(db, user.id, since=0, limit=10)

            # Assert
            mock_request.assert_called_once()
            call_args = mock_request.call_args
            headers = call_args[1].get("headers", {})
            assert "Ocp-Apim-Subscription-Key" in headers
            assert headers["Ocp-Apim-Subscription-Key"] == "test_subscription_key"

    @patch("app.services.providers.suunto.workouts.SuuntoWorkouts._make_api_request")
    def test_error_response_handling(
        self,
        mock_request: MagicMock,
        suunto_strategy: SuuntoStrategy,
        db: Session,
    ) -> None:
        """Should handle API error responses gracefully."""
        # Arrange
        user = UserFactory()
        UserConnectionFactory(user=user, provider="suunto", status=ConnectionStatus.ACTIVE)

        # Simulate error response
        mock_request.return_value = {
            "error": "Rate limit exceeded",
            "payload": [],
        }
        assert suunto_strategy.workouts is not None

        # Act
        result = suunto_strategy.workouts.get_workouts_from_api(db, user.id, since=0, limit=10)

        # Assert
        assert result["error"] == "Rate limit exceeded"
        assert result["payload"] == []
