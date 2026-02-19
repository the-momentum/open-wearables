"""
Tests for Apple Health data source handlers.

Tests cover:
- AppleSourceHandler base interface
- AutoExportHandler implementation
- HealthKitHandler implementation
- Handler normalization methods
- Data structure handling
"""

from typing import Any

import pytest

from app.services.providers.apple.handlers.auto_export import AutoExportHandler
from app.services.providers.apple.handlers.base import AppleSourceHandler
from app.services.providers.apple.handlers.healthkit import HealthKitHandler


class TestAppleSourceHandler:
    """Test suite for AppleSourceHandler base interface."""

    def test_is_abstract_class(self) -> None:
        """Should be an abstract base class."""
        # Assert
        from abc import ABC

        assert issubclass(AppleSourceHandler, ABC)

    def test_cannot_instantiate_directly(self) -> None:
        """Should not allow direct instantiation of base handler."""
        # Act & Assert
        with pytest.raises(TypeError) as exc_info:
            AppleSourceHandler()

        assert "Can't instantiate abstract class" in str(exc_info.value)

    def test_defines_normalize_method(self) -> None:
        """Should define abstract normalize method."""
        # Assert
        assert hasattr(AppleSourceHandler, "normalize")
        assert callable(getattr(AppleSourceHandler, "normalize"))


class TestAutoExportHandler:
    """Test suite for AutoExportHandler."""

    def test_is_subclass_of_base_handler(self) -> None:
        """Should be a subclass of AppleSourceHandler."""
        # Assert
        assert issubclass(AutoExportHandler, AppleSourceHandler)

    def test_initializes_successfully(self) -> None:
        """Should initialize without errors."""
        # Act
        handler = AutoExportHandler()

        # Assert
        assert handler is not None

    def test_normalize_returns_list(self) -> None:
        """Should return a list from normalize method."""
        # Arrange
        handler = AutoExportHandler()
        data: dict[str, Any] = {}

        # Act
        result = handler.normalize(data)

        # Assert
        assert isinstance(result, list)


class TestHealthKitHandler:
    """Test suite for HealthKitHandler."""

    def test_is_subclass_of_base_handler(self) -> None:
        """Should be a subclass of AppleSourceHandler."""
        # Assert
        assert issubclass(HealthKitHandler, AppleSourceHandler)

    def test_initializes_successfully(self) -> None:
        """Should initialize without errors."""
        # Act
        handler = HealthKitHandler()

        # Assert
        assert handler is not None

    def test_normalize_returns_list(self) -> None:
        """Should return a list from normalize method."""
        # Arrange
        handler = HealthKitHandler()
        data: dict[str, Any] = {}

        # Act
        result = handler.normalize(data)

        # Assert
        assert isinstance(result, list)

    def test_handler_can_process_sample_workout(self, sample_apple_healthkit_workout: dict[str, Any]) -> None:
        """Should handle sample HealthKit workout data."""
        # Arrange
        handler = HealthKitHandler()

        # Act
        result = handler.normalize(sample_apple_healthkit_workout)

        # Assert
        # Currently returns empty list as implementation is TODO
        assert isinstance(result, list)
