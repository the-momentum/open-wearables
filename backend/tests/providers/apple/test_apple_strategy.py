"""
Tests for AppleStrategy.

Tests cover:
- Strategy initialization
- Property implementations (name, display_name, api_base_url)
- Repository setup
- Cloud API capabilities
- Apple-specific behavior
"""

from app.models import EventRecord, User
from app.repositories.event_record_repository import EventRecordRepository
from app.repositories.user_connection_repository import UserConnectionRepository
from app.repositories.user_repository import UserRepository
from app.services.providers.apple.strategy import AppleStrategy
from app.services.providers.base_strategy import BaseProviderStrategy


class TestAppleStrategy:
    """Test suite for AppleStrategy."""

    def test_is_subclass_of_base_strategy(self) -> None:
        """Should be a subclass of BaseProviderStrategy."""
        # Assert
        assert issubclass(AppleStrategy, BaseProviderStrategy)

    def test_initializes_successfully(self) -> None:
        """Should initialize without errors."""
        # Act
        strategy = AppleStrategy()

        # Assert
        assert strategy is not None

    def test_initializes_repositories(self) -> None:
        """Should initialize all required repositories."""
        # Act
        strategy = AppleStrategy()

        # Assert
        assert isinstance(strategy.user_repo, UserRepository)
        assert strategy.user_repo.model == User
        assert isinstance(strategy.connection_repo, UserConnectionRepository)
        assert isinstance(strategy.workout_repo, EventRecordRepository)
        assert strategy.workout_repo.model == EventRecord

    def test_provider_name(self) -> None:
        """Should return 'apple' as provider name."""
        # Act
        strategy = AppleStrategy()

        # Assert
        assert strategy.name == "apple"

    def test_display_name(self) -> None:
        """Should return 'Apple Health' as display name."""
        # Act
        strategy = AppleStrategy()

        # Assert
        assert strategy.display_name == "Apple Health"

    def test_api_base_url(self) -> None:
        """Should return empty string for API base URL."""
        # Act
        strategy = AppleStrategy()

        # Assert
        assert strategy.api_base_url == ""

    def test_has_no_cloud_api(self) -> None:
        """Should indicate no cloud API support."""
        # Act
        strategy = AppleStrategy()

        # Assert
        assert strategy.has_cloud_api is False
        assert strategy.oauth is None

    def test_icon_url_generation(self) -> None:
        """Should generate correct icon URL path."""
        # Act
        strategy = AppleStrategy()

        # Assert
        assert strategy.icon_url == "/static/provider-icons/apple.svg"

    def test_multiple_instances_have_separate_repositories(self) -> None:
        """Should create separate repository instances for each strategy."""
        # Act
        strategy1 = AppleStrategy()
        strategy2 = AppleStrategy()

        # Assert
        assert strategy1.user_repo is not strategy2.user_repo
        assert strategy1.connection_repo is not strategy2.connection_repo
        assert strategy1.workout_repo is not strategy2.workout_repo
