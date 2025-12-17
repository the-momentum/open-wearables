"""
Tests for ProviderFactory.

Tests cover:
- Getting provider instances for all supported providers
- Provider properties and attributes
- Error handling for unknown providers
- Provider initialization and component setup
- Repository initialization
"""

import pytest

from app.services.providers.apple.strategy import AppleStrategy
from app.services.providers.base_strategy import BaseProviderStrategy
from app.services.providers.factory import ProviderFactory
from app.services.providers.garmin.strategy import GarminStrategy
from app.services.providers.polar.strategy import PolarStrategy
from app.services.providers.suunto.strategy import SuuntoStrategy


class TestProviderFactory:
    """Test suite for ProviderFactory."""

    @pytest.fixture
    def factory(self) -> ProviderFactory:
        """Create ProviderFactory instance."""
        return ProviderFactory()

    def test_get_provider_garmin(self, factory: ProviderFactory) -> None:
        """Should return GarminStrategy instance."""
        # Act
        strategy = factory.get_provider("garmin")

        # Assert
        assert isinstance(strategy, GarminStrategy)
        assert isinstance(strategy, BaseProviderStrategy)
        assert strategy.name == "garmin"

    def test_get_provider_apple(self, factory: ProviderFactory) -> None:
        """Should return AppleStrategy instance."""
        # Act
        strategy = factory.get_provider("apple")

        # Assert
        assert isinstance(strategy, AppleStrategy)
        assert isinstance(strategy, BaseProviderStrategy)
        assert strategy.name == "apple"

    def test_get_provider_polar(self, factory: ProviderFactory) -> None:
        """Should return PolarStrategy instance."""
        # Act
        strategy = factory.get_provider("polar")

        # Assert
        assert isinstance(strategy, PolarStrategy)
        assert isinstance(strategy, BaseProviderStrategy)
        assert strategy.name == "polar"

    def test_get_provider_suunto(self, factory: ProviderFactory) -> None:
        """Should return SuuntoStrategy instance."""
        # Act
        strategy = factory.get_provider("suunto")

        # Assert
        assert isinstance(strategy, SuuntoStrategy)
        assert isinstance(strategy, BaseProviderStrategy)
        assert strategy.name == "suunto"

    def test_get_provider_unknown_raises_error(self, factory: ProviderFactory) -> None:
        """Should raise ValueError for unknown provider."""
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            factory.get_provider("unknown_provider")

        assert "Unknown provider: unknown_provider" in str(exc_info.value)

    def test_get_provider_case_sensitive(self, factory: ProviderFactory) -> None:
        """Should be case-sensitive for provider names."""
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            factory.get_provider("GARMIN")

        assert "Unknown provider: GARMIN" in str(exc_info.value)

    def test_get_provider_empty_string(self, factory: ProviderFactory) -> None:
        """Should raise ValueError for empty provider name."""
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            factory.get_provider("")

        assert "Unknown provider: " in str(exc_info.value)

    def test_provider_has_repositories(self, factory: ProviderFactory) -> None:
        """Should initialize all required repositories."""
        # Act
        strategy = factory.get_provider("garmin")

        # Assert
        assert strategy.user_repo is not None
        assert strategy.connection_repo is not None
        assert strategy.workout_repo is not None

    def test_provider_garmin_has_oauth(self, factory: ProviderFactory) -> None:
        """Should initialize OAuth component for Garmin."""
        # Act
        strategy = factory.get_provider("garmin")

        # Assert
        assert strategy.oauth is not None
        assert strategy.has_cloud_api is True

    def test_provider_garmin_has_workouts(self, factory: ProviderFactory) -> None:
        """Should initialize workouts component for Garmin."""
        # Act
        strategy = factory.get_provider("garmin")

        # Assert
        assert strategy.workouts is not None

    def test_provider_apple_no_oauth(self, factory: ProviderFactory) -> None:
        """Should not have OAuth component for Apple."""
        # Act
        strategy = factory.get_provider("apple")

        # Assert
        assert strategy.oauth is None
        assert strategy.has_cloud_api is False

    def test_provider_apple_has_workouts(self, factory: ProviderFactory) -> None:
        """Should initialize workouts component for Apple."""
        # Act
        strategy = factory.get_provider("apple")

        # Assert
        assert strategy.workouts is not None

    def test_provider_polar_has_oauth(
        self, factory: ProviderFactory,
    ) -> None:
        """Should initialize OAuth component for Polar."""
        # Act
        strategy = factory.get_provider("polar")

        # Assert
        assert strategy.oauth is not None
        assert strategy.has_cloud_api is True

    def test_provider_suunto_has_oauth(
        self, factory: ProviderFactory,
    ) -> None:
        """Should initialize OAuth component for Suunto."""
        # Act
        strategy = factory.get_provider("suunto")

        # Assert
        assert strategy.oauth is not None
        assert strategy.has_cloud_api is True

    def test_multiple_calls_create_new_instances(
        self, factory: ProviderFactory,
    ) -> None:
        """Should create new instances on each call (not singleton)."""
        # Act
        strategy1 = factory.get_provider("garmin")
        strategy2 = factory.get_provider("garmin")

        # Assert
        assert strategy1 is not strategy2
        assert strategy1.name == strategy2.name
