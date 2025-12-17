"""
Tests for Polar provider strategy.

Tests the main PolarStrategy class that coordinates OAuth and workouts components.
"""

from app.repositories.event_record_repository import EventRecordRepository
from app.repositories.user_connection_repository import UserConnectionRepository
from app.repositories.user_repository import UserRepository
from app.services.providers.polar.oauth import PolarOAuth
from app.services.providers.polar.strategy import PolarStrategy
from app.services.providers.polar.workouts import PolarWorkouts


class TestPolarStrategyInitialization:
    """Tests for PolarStrategy initialization and configuration."""

    def test_polar_strategy_initialization(self) -> None:
        """Test PolarStrategy initializes correctly with all components."""
        # Act
        strategy = PolarStrategy()

        # Assert
        assert strategy is not None
        assert strategy.oauth is not None
        assert strategy.workouts is not None
        assert isinstance(strategy.oauth, PolarOAuth)
        assert isinstance(strategy.workouts, PolarWorkouts)

    def test_polar_strategy_has_required_repositories(self) -> None:
        """Test PolarStrategy initializes required repositories."""
        # Act
        strategy = PolarStrategy()

        # Assert
        assert strategy.user_repo is not None
        assert strategy.connection_repo is not None
        assert strategy.workout_repo is not None
        assert isinstance(strategy.user_repo, UserRepository)
        assert isinstance(strategy.connection_repo, UserConnectionRepository)
        assert isinstance(strategy.workout_repo, EventRecordRepository)

    def test_polar_strategy_name_property(self) -> None:
        """Test PolarStrategy returns correct provider name."""
        # Arrange
        strategy = PolarStrategy()

        # Act
        name = strategy.name

        # Assert
        assert name == "polar"
        assert isinstance(name, str)

    def test_polar_strategy_api_base_url_property(self) -> None:
        """Test PolarStrategy returns correct API base URL."""
        # Arrange
        strategy = PolarStrategy()

        # Act
        api_base_url = strategy.api_base_url

        # Assert
        assert api_base_url == "https://www.polaraccesslink.com"
        assert isinstance(api_base_url, str)
        assert api_base_url.startswith("https://")

    def test_polar_strategy_display_name(self) -> None:
        """Test PolarStrategy has correct display name."""
        # Arrange
        strategy = PolarStrategy()

        # Act
        display_name = strategy.display_name

        # Assert
        assert display_name == "Polar"
        assert isinstance(display_name, str)

    def test_polar_strategy_has_cloud_api(self) -> None:
        """Test PolarStrategy indicates it has cloud API."""
        # Arrange
        strategy = PolarStrategy()

        # Act
        has_cloud_api = strategy.has_cloud_api

        # Assert
        assert has_cloud_api is True

    def test_polar_strategy_icon_url(self) -> None:
        """Test PolarStrategy returns correct icon URL."""
        # Arrange
        strategy = PolarStrategy()

        # Act
        icon_url = strategy.icon_url

        # Assert
        assert icon_url == "/static/provider-icons/polar.svg"
        assert "polar" in icon_url


class TestPolarStrategyComponents:
    """Tests for PolarStrategy component integration."""

    def test_oauth_component_configuration(self) -> None:
        """Test OAuth component is properly configured with strategy settings."""
        # Arrange
        strategy = PolarStrategy()

        # Assert
        assert strategy.oauth.provider_name == "polar"
        assert strategy.oauth.api_base_url == "https://www.polaraccesslink.com"
        assert strategy.oauth.user_repo is strategy.user_repo
        assert strategy.oauth.connection_repo is strategy.connection_repo

    def test_workouts_component_configuration(self) -> None:
        """Test workouts component is properly configured with strategy settings."""
        # Arrange
        strategy = PolarStrategy()

        # Assert
        assert strategy.workouts.provider_name == "polar"
        assert strategy.workouts.api_base_url == "https://www.polaraccesslink.com"
        assert strategy.workouts.workout_repo is strategy.workout_repo
        assert strategy.workouts.connection_repo is strategy.connection_repo
        assert strategy.workouts.oauth is strategy.oauth

    def test_strategy_components_share_repositories(self) -> None:
        """Test that OAuth and workouts components share the same repository instances."""
        # Arrange
        strategy = PolarStrategy()

        # Assert - Components should share the same repository instances
        assert strategy.oauth.user_repo is strategy.user_repo
        assert strategy.oauth.connection_repo is strategy.connection_repo
        assert strategy.workouts.connection_repo is strategy.connection_repo
        assert strategy.workouts.workout_repo is strategy.workout_repo
