"""
Tests for SuuntoStrategy.

Tests cover:
- Strategy initialization
- Provider properties (name, API base URL)
- OAuth component initialization
- Workouts component initialization
- Repository initialization
- Cloud API support
"""


from app.models import EventRecord, User
from app.repositories.event_record_repository import EventRecordRepository
from app.repositories.user_connection_repository import UserConnectionRepository
from app.repositories.user_repository import UserRepository
from app.services.providers.suunto.oauth import SuuntoOAuth
from app.services.providers.suunto.strategy import SuuntoStrategy
from app.services.providers.suunto.workouts import SuuntoWorkouts


class TestSuuntoStrategy:
    """Test suite for SuuntoStrategy."""

    def test_strategy_initializes_repositories(self) -> None:
        """Should initialize all repositories on SuuntoStrategy."""
        # Act
        strategy = SuuntoStrategy()

        # Assert
        assert isinstance(strategy.user_repo, UserRepository)
        assert strategy.user_repo.model == User
        assert isinstance(strategy.connection_repo, UserConnectionRepository)
        assert isinstance(strategy.workout_repo, EventRecordRepository)
        assert strategy.workout_repo.model == EventRecord

    def test_strategy_initializes_oauth_component(self) -> None:
        """Should initialize OAuth component with correct configuration."""
        # Act
        strategy = SuuntoStrategy()

        # Assert
        assert isinstance(strategy.oauth, SuuntoOAuth)
        assert strategy.oauth.provider_name == "suunto"
        assert strategy.oauth.api_base_url == "https://cloudapi.suunto.com"

    def test_strategy_initializes_workouts_component(self) -> None:
        """Should initialize workouts component with correct configuration."""
        # Act
        strategy = SuuntoStrategy()

        # Assert
        assert isinstance(strategy.workouts, SuuntoWorkouts)
        assert strategy.workouts.provider_name == "suunto"
        assert strategy.workouts.api_base_url == "https://cloudapi.suunto.com"
        assert strategy.workouts.oauth == strategy.oauth

    def test_provider_name(self) -> None:
        """Should return correct provider name."""
        # Act
        strategy = SuuntoStrategy()

        # Assert
        assert strategy.name == "suunto"

    def test_api_base_url(self) -> None:
        """Should return correct API base URL."""
        # Act
        strategy = SuuntoStrategy()

        # Assert
        assert strategy.api_base_url == "https://cloudapi.suunto.com"

    def test_display_name(self) -> None:
        """Should return capitalized display name."""
        # Act
        strategy = SuuntoStrategy()

        # Assert
        assert strategy.display_name == "Suunto"

    def test_has_cloud_api(self) -> None:
        """Should return True for has_cloud_api when OAuth is present."""
        # Act
        strategy = SuuntoStrategy()

        # Assert
        assert strategy.has_cloud_api is True
        assert strategy.oauth is not None

    def test_icon_url_generation(self) -> None:
        """Should generate correct icon URL path."""
        # Act
        strategy = SuuntoStrategy()

        # Assert
        assert strategy.icon_url == "/static/provider-icons/suunto.svg"

    def test_workouts_component_receives_repositories(self) -> None:
        """Should pass repositories to workouts component."""
        # Act
        strategy = SuuntoStrategy()

        # Assert
        assert strategy.workouts.workout_repo == strategy.workout_repo
        assert strategy.workouts.connection_repo == strategy.connection_repo

    def test_oauth_component_receives_repositories(self) -> None:
        """Should pass repositories to OAuth component."""
        # Act
        strategy = SuuntoStrategy()

        # Assert
        assert strategy.oauth.user_repo == strategy.user_repo
        assert strategy.oauth.connection_repo == strategy.connection_repo
