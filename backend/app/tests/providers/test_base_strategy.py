"""
Tests for BaseProviderStrategy.

Tests cover:
- Abstract properties and methods
- Concrete property implementations
- Repository initialization
- Component attributes
- Display names and icons
"""

from abc import ABC

import pytest

from app.models import EventRecord, User
from app.repositories.event_record_repository import EventRecordRepository
from app.repositories.user_connection_repository import UserConnectionRepository
from app.repositories.user_repository import UserRepository
from app.services.providers.apple.strategy import AppleStrategy
from app.services.providers.base_strategy import BaseProviderStrategy
from app.services.providers.garmin.strategy import GarminStrategy
from app.services.providers.polar.strategy import PolarStrategy
from app.services.providers.suunto.strategy import SuuntoStrategy


class TestBaseProviderStrategy:
    """Test suite for BaseProviderStrategy."""

    def test_is_abstract_class(self):
        """Should be an abstract base class."""
        # Assert
        assert issubclass(BaseProviderStrategy, ABC)

    def test_cannot_instantiate_directly(self):
        """Should not allow direct instantiation."""
        # Act & Assert
        with pytest.raises(TypeError) as exc_info:
            BaseProviderStrategy()

        assert "Can't instantiate abstract class" in str(exc_info.value)

    def test_garmin_strategy_initializes_repositories(self):
        """Should initialize all repositories on GarminStrategy."""
        # Act
        strategy = GarminStrategy()

        # Assert
        assert isinstance(strategy.user_repo, UserRepository)
        assert strategy.user_repo.model == User
        assert isinstance(strategy.connection_repo, UserConnectionRepository)
        assert isinstance(strategy.workout_repo, EventRecordRepository)
        assert strategy.workout_repo.model == EventRecord

    def test_apple_strategy_initializes_repositories(self):
        """Should initialize all repositories on AppleStrategy."""
        # Act
        strategy = AppleStrategy()

        # Assert
        assert isinstance(strategy.user_repo, UserRepository)
        assert isinstance(strategy.connection_repo, UserConnectionRepository)
        assert isinstance(strategy.workout_repo, EventRecordRepository)

    def test_garmin_provider_name(self):
        """Should return correct provider name for Garmin."""
        # Act
        strategy = GarminStrategy()

        # Assert
        assert strategy.name == "garmin"

    def test_garmin_api_base_url(self):
        """Should return correct API base URL for Garmin."""
        # Act
        strategy = GarminStrategy()

        # Assert
        assert strategy.api_base_url == "https://apis.garmin.com"

    def test_garmin_display_name(self):
        """Should return capitalized display name for Garmin."""
        # Act
        strategy = GarminStrategy()

        # Assert
        assert strategy.display_name == "Garmin"

    def test_apple_display_name_override(self):
        """Should return custom display name for Apple."""
        # Act
        strategy = AppleStrategy()

        # Assert
        assert strategy.display_name == "Apple Health"

    def test_garmin_has_cloud_api(self):
        """Should return True for has_cloud_api when OAuth is present."""
        # Act
        strategy = GarminStrategy()

        # Assert
        assert strategy.has_cloud_api is True
        assert strategy.oauth is not None

    def test_apple_no_cloud_api(self):
        """Should return False for has_cloud_api when OAuth is absent."""
        # Act
        strategy = AppleStrategy()

        # Assert
        assert strategy.has_cloud_api is False
        assert strategy.oauth is None

    def test_icon_url_generation(self):
        """Should generate correct icon URL path."""
        # Act
        garmin_strategy = GarminStrategy()
        apple_strategy = AppleStrategy()
        polar_strategy = PolarStrategy()
        suunto_strategy = SuuntoStrategy()

        # Assert
        assert garmin_strategy.icon_url == "/static/provider-icons/garmin.svg"
        assert apple_strategy.icon_url == "/static/provider-icons/apple.svg"
        assert polar_strategy.icon_url == "/static/provider-icons/polar.svg"
        assert suunto_strategy.icon_url == "/static/provider-icons/suunto.svg"
