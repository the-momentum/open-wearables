"""
Tests for base template classes.

Tests cover:
- BaseOAuthTemplate abstract interface
- BaseWorkoutsTemplate abstract interface
- Template method pattern implementation
- Abstract method enforcement
- Repository integration
"""

from abc import ABC
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.models import User
from app.repositories.event_record_repository import EventRecordRepository
from app.repositories.user_connection_repository import UserConnectionRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import ConnectionStatus
from app.schemas.model_crud.activities import EventRecordCreate, EventRecordDetailCreate
from app.schemas.model_crud.credentials import OAuthState, OAuthTokenResponse
from app.services.providers.garmin.oauth import GarminOAuth
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.services.providers.templates.base_workouts import BaseWorkoutsTemplate
from tests.factories import UserConnectionFactory, UserFactory


class TestBaseOAuthTemplate:
    """Test suite for BaseOAuthTemplate."""

    def test_is_abstract_class(self) -> None:
        """Should be an abstract base class."""
        # Assert
        assert issubclass(BaseOAuthTemplate, ABC)

    def test_cannot_instantiate_directly(self) -> None:
        """Should not allow direct instantiation."""
        # Arrange
        mock_user_repo = MagicMock(spec=UserRepository)
        mock_connection_repo = MagicMock(spec=UserConnectionRepository)

        # Act & Assert
        with pytest.raises(TypeError) as exc_info:
            BaseOAuthTemplate(
                user_repo=mock_user_repo,
                connection_repo=mock_connection_repo,
                provider_name="test",
                api_base_url="https://api.test.com",
            )

        assert "Can't instantiate abstract class" in str(exc_info.value)

    def test_has_required_abstract_properties(self) -> None:
        """Should define required abstract properties."""
        # Assert
        assert hasattr(BaseOAuthTemplate, "endpoints")
        assert hasattr(BaseOAuthTemplate, "credentials")

    def test_default_pkce_disabled(self) -> None:
        """Should have PKCE disabled by default."""
        # Assert
        assert BaseOAuthTemplate.use_pkce is False


class TestBaseWorkoutsTemplate:
    """Test suite for BaseWorkoutsTemplate."""

    def test_is_abstract_class(self) -> None:
        """Should be an abstract base class."""
        # Assert
        assert issubclass(BaseWorkoutsTemplate, ABC)

    def test_cannot_instantiate_directly(self) -> None:
        """Should not allow direct instantiation."""
        # Arrange
        mock_workout_repo = MagicMock(spec=EventRecordRepository)
        mock_connection_repo = MagicMock(spec=UserConnectionRepository)
        mock_oauth = MagicMock(spec=BaseOAuthTemplate)

        # Act & Assert
        with pytest.raises(TypeError) as exc_info:
            BaseWorkoutsTemplate(
                workout_repo=mock_workout_repo,
                connection_repo=mock_connection_repo,
                provider_name="test",
                api_base_url="https://api.test.com",
                oauth=mock_oauth,
            )

        assert "Can't instantiate abstract class" in str(exc_info.value)

    def test_has_required_abstract_methods(self) -> None:
        """Should define required abstract methods."""
        # Assert
        assert hasattr(BaseWorkoutsTemplate, "get_workouts")
        assert hasattr(BaseWorkoutsTemplate, "_normalize_workout")
        assert callable(getattr(BaseWorkoutsTemplate, "get_workouts"))
        assert callable(getattr(BaseWorkoutsTemplate, "_normalize_workout"))

    def test_extract_dates_default_implementation(self) -> None:
        """Should have default _extract_dates implementation for datetime objects."""
        # This test verifies the documented behavior in base template

        # Create a concrete implementation for testing
        class ConcreteWorkoutsTemplate(BaseWorkoutsTemplate):
            def get_workouts(self, db: Any, user_id: Any, start_date: Any, end_date: Any) -> list:
                return []

            def _normalize_workout(
                self,
                raw_workout: Any,
                user_id: Any,
            ) -> tuple[EventRecordCreate, EventRecordDetailCreate]:
                raise NotImplementedError("Test implementation")

        # Arrange
        mock_workout_repo = MagicMock(spec=EventRecordRepository)
        mock_connection_repo = MagicMock(spec=UserConnectionRepository)
        mock_oauth = MagicMock()

        template = ConcreteWorkoutsTemplate(
            workout_repo=mock_workout_repo,
            connection_repo=mock_connection_repo,
            provider_name="test",
            api_base_url="https://api.test.com",
            oauth=mock_oauth,
        )

        start = datetime(2024, 1, 15, 8, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc)

        # Act
        result_start, result_end = template._extract_dates(start, end)

        # Assert
        assert result_start == start
        assert result_end == end


class TestSaveConnectionEmitsEvents:
    """_save_connection must emit connection.created on BOTH branches.

    The reconnect branch (existing row, e.g. after a revoked/expired
    connection) historically updated the tokens silently: consumers that
    reacted to connection.revoked never learned the connection was usable
    again and stayed stuck on their "disconnected" state (#1255 follow-up,
    Bazard BAZ-453).
    """

    @pytest.fixture
    def oauth_service(self, db: Session) -> GarminOAuth:
        """Concrete BaseOAuthTemplate vehicle (Garmin) with real repos."""
        return GarminOAuth(
            user_repo=UserRepository(User),
            connection_repo=UserConnectionRepository(),
            provider_name="garmin",
            api_base_url="https://apis.garmin.com",
        )

    @staticmethod
    def _token_response() -> OAuthTokenResponse:
        return OAuthTokenResponse(
            access_token="fresh_access_token",
            token_type="Bearer",
            expires_in=3600,
            refresh_token="fresh_refresh_token",
        )

    @patch("app.services.providers.templates.base_oauth.on_connection_created")
    def test_reconnect_emits_connection_created_and_reactivates(
        self,
        mock_emit: MagicMock,
        oauth_service: GarminOAuth,
        db: Session,
    ) -> None:
        """Re-authorizing over a revoked connection emits the event again."""
        user = UserFactory()
        connection = UserConnectionFactory(
            user=user,
            provider="garmin",
            status=ConnectionStatus.REVOKED,
        )

        oauth_service._save_connection(
            db,
            user.id,
            self._token_response(),
            {"user_id": None, "username": None},
            OAuthState(user_id=user.id, provider="garmin"),
        )

        mock_emit.assert_called_once()
        kwargs = mock_emit.call_args.kwargs
        assert kwargs["user_id"] == user.id
        assert kwargs["provider"] == "garmin"
        assert kwargs["connection_id"] == connection.id
        assert kwargs["connected_at"]  # timestamp-scoped: distinct Svix event id

        db.refresh(connection)
        assert connection.status == ConnectionStatus.ACTIVE
        assert connection.access_token == "fresh_access_token"

    @patch("app.services.providers.templates.base_oauth.on_connection_created")
    def test_first_connect_still_emits_connection_created(
        self,
        mock_emit: MagicMock,
        oauth_service: GarminOAuth,
        db: Session,
    ) -> None:
        """Regression guard: the historical first-connect emit is unchanged."""
        user = UserFactory()

        oauth_service._save_connection(
            db,
            user.id,
            self._token_response(),
            {"user_id": "garmin-user-1", "username": "runner"},
            OAuthState(user_id=user.id, provider="garmin"),
        )

        mock_emit.assert_called_once()
        assert mock_emit.call_args.kwargs["provider"] == "garmin"
