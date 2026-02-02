"""
Tests for ProviderSettingsService.

Tests cover:
- Getting all providers with their settings
- Updating individual provider status
- Bulk updating provider settings
- Validation of provider names
"""

import pytest
from sqlalchemy.orm import Session

from app.schemas import ProviderName, ProviderSettingUpdate
from app.services.provider_settings_service import ProviderSettingsService


class TestProviderSettingsServiceGetAllProviders:
    """Test getting all providers."""

    def test_get_all_providers_returns_all_provider_types(self, db: Session) -> None:
        """Should return all provider types defined in ProviderName enum."""
        # Arrange
        service = ProviderSettingsService()

        # Act
        providers = service.get_all_providers(db)

        # Assert
        provider_names = {p.provider for p in providers}
        expected_names = {p.value for p in ProviderName if p.value != "unknown"}
        assert provider_names == expected_names

    def test_get_all_providers_includes_display_name(self, db: Session) -> None:
        """Should include display name for each provider."""
        # Arrange
        service = ProviderSettingsService()

        # Act
        providers = service.get_all_providers(db)

        # Assert
        for provider in providers:
            assert provider.name is not None
            assert len(provider.name) > 0

    def test_get_all_providers_includes_has_cloud_api(self, db: Session) -> None:
        """Should include has_cloud_api flag for each provider."""
        # Arrange
        service = ProviderSettingsService()

        # Act
        providers = service.get_all_providers(db)

        # Assert
        for provider in providers:
            assert isinstance(provider.has_cloud_api, bool)

    def test_get_all_providers_includes_icon_url(self, db: Session) -> None:
        """Should include icon_url for each provider."""
        # Arrange
        service = ProviderSettingsService()

        # Act
        providers = service.get_all_providers(db)

        # Assert
        for provider in providers:
            # icon_url can be None or a string
            assert provider.icon_url is None or isinstance(provider.icon_url, str)

    def test_get_all_providers_default_enabled_true(self, db: Session) -> None:
        """Should default to enabled=True when no database setting exists."""
        # Arrange
        service = ProviderSettingsService()

        # Act
        providers = service.get_all_providers(db)

        # Assert
        # All providers should be enabled by default
        for provider in providers:
            assert provider.is_enabled is True

    def test_get_all_providers_merges_database_settings(self, db: Session) -> None:
        """Should merge database settings with provider strategies."""
        # Arrange
        service = ProviderSettingsService()

        # Disable one provider
        update = ProviderSettingUpdate(is_enabled=False)
        service.update_provider_status(db, "apple", update)

        # Act
        providers = service.get_all_providers(db)

        # Assert
        apple_provider = next(p for p in providers if p.provider == "apple")
        assert apple_provider.is_enabled is False

        # Other providers should still be enabled
        other_providers = [p for p in providers if p.provider != "apple"]
        for provider in other_providers:
            assert provider.is_enabled is True


class TestProviderSettingsServiceUpdateProviderStatus:
    """Test updating individual provider status."""

    def test_update_provider_status_enable_to_disable(self, db: Session) -> None:
        """Should update provider from enabled to disabled."""
        # Arrange
        service = ProviderSettingsService()
        update = ProviderSettingUpdate(is_enabled=False)

        # Act
        result = service.update_provider_status(db, "garmin", update)

        # Assert
        assert result.provider == "garmin"
        assert result.is_enabled is False

        # Verify it persists
        providers = service.get_all_providers(db)
        garmin = next(p for p in providers if p.provider == "garmin")
        assert garmin.is_enabled is False

    def test_update_provider_status_disable_to_enable(self, db: Session) -> None:
        """Should update provider from disabled to enabled."""
        # Arrange
        service = ProviderSettingsService()

        # First disable
        service.update_provider_status(db, "polar", ProviderSettingUpdate(is_enabled=False))

        # Act - re-enable
        result = service.update_provider_status(db, "polar", ProviderSettingUpdate(is_enabled=True))

        # Assert
        assert result.provider == "polar"
        assert result.is_enabled is True

    def test_update_provider_status_includes_metadata(self, db: Session) -> None:
        """Should return provider metadata along with status."""
        # Arrange
        service = ProviderSettingsService()
        update = ProviderSettingUpdate(is_enabled=False)

        # Act
        result = service.update_provider_status(db, "apple", update)

        # Assert
        assert result.provider == "apple"
        assert result.name is not None
        assert isinstance(result.has_cloud_api, bool)

    def test_update_provider_status_invalid_provider_raises_error(self, db: Session) -> None:
        """Should raise ValueError for invalid provider name."""
        # Arrange
        service = ProviderSettingsService()
        update = ProviderSettingUpdate(is_enabled=False)

        # Act & Assert
        with pytest.raises(ValueError, match="Unknown provider"):
            service.update_provider_status(db, "invalid_provider", update)

    def test_update_provider_status_case_sensitive(self, db: Session) -> None:
        """Should handle provider names case-sensitively."""
        # Arrange
        service = ProviderSettingsService()
        update = ProviderSettingUpdate(is_enabled=False)

        # Act & Assert - uppercase should fail
        with pytest.raises(ValueError, match="Unknown provider"):
            service.update_provider_status(db, "APPLE", update)


class TestProviderSettingsServiceBulkUpdateProviders:
    """Test bulk updating provider settings."""

    def test_bulk_update_providers_multiple_updates(self, db: Session) -> None:
        """Should update multiple providers at once."""
        # Arrange
        service = ProviderSettingsService()
        updates = {
            "apple": False,
            "garmin": False,
            "polar": True,
        }

        # Act
        results = service.bulk_update_providers(db, updates)

        # Assert
        results_dict = {p.provider: p.is_enabled for p in results}
        assert results_dict["apple"] is False
        assert results_dict["garmin"] is False
        assert results_dict["polar"] is True

    def test_bulk_update_providers_validates_all_before_updating(self, db: Session) -> None:
        """Should validate all provider names before applying any updates."""
        # Arrange
        service = ProviderSettingsService()
        updates = {
            "apple": False,
            "invalid_provider": True,  # Invalid provider
        }

        # Act & Assert
        with pytest.raises(ValueError, match="Unknown provider"):
            service.bulk_update_providers(db, updates)

        # Verify no updates were applied (transaction rolled back)
        providers = service.get_all_providers(db)
        apple = next(p for p in providers if p.provider == "apple")
        assert apple.is_enabled is True  # Should remain enabled

    def test_bulk_update_providers_empty_updates(self, db: Session) -> None:
        """Should handle empty update dictionary."""
        # Arrange
        service = ProviderSettingsService()
        updates = {}

        # Act
        results = service.bulk_update_providers(db, updates)

        # Assert
        # Should return all providers with their current settings
        assert len(results) == len(list(ProviderName)) - 1

    def test_bulk_update_providers_single_update(self, db: Session) -> None:
        """Should handle single provider update."""
        # Arrange
        service = ProviderSettingsService()
        updates = {"suunto": False}

        # Act
        results = service.bulk_update_providers(db, updates)

        # Assert
        suunto = next(p for p in results if p.provider == "suunto")
        assert suunto.is_enabled is False

        # Other providers should remain at default (enabled)
        others = [p for p in results if p.provider != "suunto"]
        for provider in others:
            assert provider.is_enabled is True

    def test_bulk_update_providers_returns_all_providers(self, db: Session) -> None:
        """Should return all providers after bulk update."""
        # Arrange
        service = ProviderSettingsService()
        updates = {"apple": False}

        # Act
        results = service.bulk_update_providers(db, updates)

        # Assert
        # Should return all provider types
        provider_names = {p.provider for p in results}
        expected_names = {p.value for p in ProviderName if p.value != "unknown"}
        assert provider_names == expected_names

    def test_bulk_update_providers_validates_first_then_updates(self, db: Session) -> None:
        """Should validate all providers exist before making any changes."""
        # Arrange
        service = ProviderSettingsService()

        # First, set apple to disabled
        service.update_provider_status(db, "apple", ProviderSettingUpdate(is_enabled=False))

        # Try bulk update with invalid provider
        updates = {
            "apple": True,  # Valid
            "fake_provider": False,  # Invalid
        }

        # Act & Assert
        with pytest.raises(ValueError, match="Unknown provider"):
            service.bulk_update_providers(db, updates)

        # Verify apple is still disabled (update didn't go through)
        providers = service.get_all_providers(db)
        apple = next(p for p in providers if p.provider == "apple")
        assert apple.is_enabled is False


class TestProviderSettingsServiceProviderFactory:
    """Test provider factory integration."""

    def test_get_all_providers_uses_factory_metadata(self, db: Session) -> None:
        """Should use provider factory for display names and metadata."""
        # Arrange
        service = ProviderSettingsService()

        # Act
        providers = service.get_all_providers(db)

        # Assert
        # Verify each provider has metadata from factory
        for provider in providers:
            assert provider.provider in [p.value for p in ProviderName]
            assert provider.name is not None  # From factory
            assert isinstance(provider.has_cloud_api, bool)  # From factory

    def test_update_provider_validates_against_factory(self, db: Session) -> None:
        """Should validate provider exists in factory."""
        # Arrange
        service = ProviderSettingsService()
        update = ProviderSettingUpdate(is_enabled=False)

        # Act & Assert
        with pytest.raises(ValueError, match="Unknown provider"):
            service.update_provider_status(db, "nonexistent", update)
