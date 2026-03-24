"""
Tests for Ultrahuman provider strategy.

Tests the UltrahumanStrategy class for provider initialization and component setup.
"""

from sqlalchemy.orm import Session

from app.services.providers.base_strategy import BaseProviderStrategy
from app.services.providers.ultrahuman.strategy import UltrahumanStrategy


class TestUltrahumanStrategy:
    """Test suite for UltrahumanStrategy."""

    def test_ultrahuman_strategy_initialization(self, db: Session) -> None:
        """Should initialize UltrahumanStrategy successfully."""
        # Act
        strategy = UltrahumanStrategy()

        # Assert
        assert isinstance(strategy, BaseProviderStrategy)
        assert isinstance(strategy, UltrahumanStrategy)

    def test_ultrahuman_strategy_name(self, db: Session) -> None:
        """Should return correct provider name."""
        # Arrange
        strategy = UltrahumanStrategy()

        # Act
        name = strategy.name

        # Assert
        assert name == "ultrahuman"

    def test_ultrahuman_strategy_api_base_url(self, db: Session) -> None:
        """Should return correct API base URL."""
        # Arrange
        strategy = UltrahumanStrategy()

        # Act
        api_base_url = strategy.api_base_url

        # Assert
        assert api_base_url == "https://partner.ultrahuman.com/api/partners/v1"

    def test_ultrahuman_strategy_display_name(self, db: Session) -> None:
        """Should return correct display name."""
        # Arrange
        strategy = UltrahumanStrategy()

        # Act
        display_name = strategy.display_name

        # Assert
        assert display_name == "Ultrahuman"

    def test_ultrahuman_strategy_has_oauth(self, db: Session) -> None:
        """Should initialize OAuth component."""
        # Arrange
        strategy = UltrahumanStrategy()

        # Assert
        assert strategy.oauth is not None
        assert strategy.has_cloud_api is True

    def test_ultrahuman_strategy_has_data_247(self, db: Session) -> None:
        """Should initialize data_247 component."""
        # Arrange
        strategy = UltrahumanStrategy()

        # Assert
        assert strategy.data_247 is not None

    def test_ultrahuman_strategy_has_repositories(self, db: Session) -> None:
        """Should initialize all required repositories."""
        # Arrange
        strategy = UltrahumanStrategy()

        # Assert
        assert strategy.user_repo is not None
        assert strategy.connection_repo is not None
        assert strategy.workout_repo is not None

    def test_ultrahuman_strategy_icon_url(self, db: Session) -> None:
        """Should return correct icon URL."""
        # Arrange
        strategy = UltrahumanStrategy()

        # Act
        icon_url = strategy.icon_url

        # Assert
        assert icon_url == "/static/provider-icons/ultrahuman.svg"
