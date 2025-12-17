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
from unittest.mock import MagicMock

import pytest

from app.repositories.event_record_repository import EventRecordRepository
from app.repositories.user_connection_repository import UserConnectionRepository
from app.repositories.user_repository import UserRepository
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.services.providers.templates.base_workouts import BaseWorkoutsTemplate


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

            def _normalize_workout(self, raw_workout: Any, user_id: Any) -> None:
                pass

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
