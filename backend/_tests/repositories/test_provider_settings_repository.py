"""
Tests for ProviderSettingsRepository.

Tests cover:
- get_all operations (empty database, single setting, multiple settings)
- upsert operations (insert new, update existing, toggle enabled/disabled)
- ensure_all_providers_exist (empty database, partial existing, all existing)
- bulk_update operations (multiple providers, mixed updates)
"""

import pytest
from sqlalchemy.orm import Session

from app.repositories.provider_settings_repository import ProviderSettingsRepository
from _tests.factories import ProviderSettingFactory


class TestProviderSettingsRepository:
    """Test suite for ProviderSettingsRepository."""

    @pytest.fixture
    def provider_repo(self) -> ProviderSettingsRepository:
        """Create ProviderSettingsRepository instance."""
        return ProviderSettingsRepository()

    def test_get_all_empty_database(self, db: Session, provider_repo: ProviderSettingsRepository) -> None:
        """Test get_all returns empty dict when no settings exist."""
        # Act
        result = provider_repo.get_all(db)

        # Assert
        assert result == {}

    def test_get_all_single_setting(self, db: Session, provider_repo: ProviderSettingsRepository) -> None:
        """Test get_all returns single provider setting."""
        # Arrange
        ProviderSettingFactory(provider="garmin", is_enabled=True)

        # Act
        result = provider_repo.get_all(db)

        # Assert
        assert len(result) == 1
        assert result["garmin"] is True

    def test_get_all_multiple_settings(self, db: Session, provider_repo: ProviderSettingsRepository) -> None:
        """Test get_all returns multiple provider settings."""
        # Arrange
        ProviderSettingFactory(provider="garmin", is_enabled=True)
        ProviderSettingFactory(provider="apple", is_enabled=False)
        ProviderSettingFactory(provider="fitbit", is_enabled=True)

        # Act
        result = provider_repo.get_all(db)

        # Assert
        assert len(result) == 3
        assert result["garmin"] is True
        assert result["apple"] is False
        assert result["fitbit"] is True

    def test_upsert_creates_new_provider(self, db: Session, provider_repo: ProviderSettingsRepository) -> None:
        """Test upsert creates a new provider setting when it doesn't exist."""
        # Act
        result = provider_repo.upsert(db, provider="strava", is_enabled=True)

        # Assert
        assert result.provider == "strava"
        assert result.is_enabled is True

        # Verify in database
        db.expire_all()
        all_settings = provider_repo.get_all(db)
        assert "strava" in all_settings
        assert all_settings["strava"] is True

    def test_upsert_updates_existing_provider(self, db: Session, provider_repo: ProviderSettingsRepository) -> None:
        """Test upsert updates an existing provider setting."""
        # Arrange
        ProviderSettingFactory(provider="garmin", is_enabled=True)

        # Act - Update to disabled
        result = provider_repo.upsert(db, provider="garmin", is_enabled=False)

        # Assert
        assert result.provider == "garmin"
        assert result.is_enabled is False

        # Verify in database
        db.expire_all()
        all_settings = provider_repo.get_all(db)
        assert all_settings["garmin"] is False

    def test_upsert_toggle_enabled_to_disabled(self, db: Session, provider_repo: ProviderSettingsRepository) -> None:
        """Test upsert can toggle a provider from enabled to disabled."""
        # Arrange
        ProviderSettingFactory(provider="apple", is_enabled=True)

        # Act
        result = provider_repo.upsert(db, provider="apple", is_enabled=False)

        # Assert
        assert result.is_enabled is False
        db.expire_all()
        assert provider_repo.get_all(db)["apple"] is False

    def test_upsert_toggle_disabled_to_enabled(self, db: Session, provider_repo: ProviderSettingsRepository) -> None:
        """Test upsert can toggle a provider from disabled to enabled."""
        # Arrange
        ProviderSettingFactory(provider="fitbit", is_enabled=False)

        # Act
        result = provider_repo.upsert(db, provider="fitbit", is_enabled=True)

        # Assert
        assert result.is_enabled is True
        db.expire_all()
        assert provider_repo.get_all(db)["fitbit"] is True

    def test_ensure_all_providers_exist_empty_database(
        self,
        db: Session,
        provider_repo: ProviderSettingsRepository,
    ) -> None:
        """Test ensure_all_providers_exist adds all providers when database is empty."""
        # Arrange
        providers = ["garmin", "apple", "fitbit", "strava"]

        # Act
        provider_repo.ensure_all_providers_exist(db, providers)

        # Assert
        db.expire_all()
        all_settings = provider_repo.get_all(db)
        assert len(all_settings) == 4
        for provider in providers:
            assert provider in all_settings
            assert all_settings[provider] is True  # Default enabled

    def test_ensure_all_providers_exist_partial_existing(
        self,
        db: Session,
        provider_repo: ProviderSettingsRepository,
    ) -> None:
        """Test ensure_all_providers_exist adds only missing providers."""
        # Arrange
        ProviderSettingFactory(provider="garmin", is_enabled=False)
        ProviderSettingFactory(provider="apple", is_enabled=True)
        providers = ["garmin", "apple", "fitbit", "strava"]

        # Act
        provider_repo.ensure_all_providers_exist(db, providers)

        # Assert
        db.expire_all()
        all_settings = provider_repo.get_all(db)
        assert len(all_settings) == 4
        # Existing providers should keep their settings
        assert all_settings["garmin"] is False
        assert all_settings["apple"] is True
        # New providers should be enabled by default
        assert all_settings["fitbit"] is True
        assert all_settings["strava"] is True

    def test_ensure_all_providers_exist_all_existing(
        self,
        db: Session,
        provider_repo: ProviderSettingsRepository,
    ) -> None:
        """Test ensure_all_providers_exist does nothing when all providers exist."""
        # Arrange
        ProviderSettingFactory(provider="garmin", is_enabled=False)
        ProviderSettingFactory(provider="apple", is_enabled=True)
        providers = ["garmin", "apple"]

        # Act
        provider_repo.ensure_all_providers_exist(db, providers)

        # Assert
        db.expire_all()
        all_settings = provider_repo.get_all(db)
        assert len(all_settings) == 2
        # Settings should remain unchanged
        assert all_settings["garmin"] is False
        assert all_settings["apple"] is True

    def test_bulk_update_multiple_providers(self, db: Session, provider_repo: ProviderSettingsRepository) -> None:
        """Test bulk_update updates multiple providers at once."""
        # Arrange
        ProviderSettingFactory(provider="garmin", is_enabled=True)
        ProviderSettingFactory(provider="apple", is_enabled=True)

        # Act
        updates = {"garmin": False, "apple": False, "fitbit": True}
        provider_repo.bulk_update(db, updates)

        # Assert
        db.expire_all()
        all_settings = provider_repo.get_all(db)
        assert all_settings["garmin"] is False
        assert all_settings["apple"] is False
        assert all_settings["fitbit"] is True

    def test_bulk_update_mixed_insert_and_update(self, db: Session, provider_repo: ProviderSettingsRepository) -> None:
        """Test bulk_update can both insert new providers and update existing ones."""
        # Arrange
        ProviderSettingFactory(provider="garmin", is_enabled=True)

        # Act - Update existing and insert new
        updates = {"garmin": False, "strava": True, "fitbit": False}
        provider_repo.bulk_update(db, updates)

        # Assert
        db.expire_all()
        all_settings = provider_repo.get_all(db)
        assert len(all_settings) == 3
        assert all_settings["garmin"] is False
        assert all_settings["strava"] is True
        assert all_settings["fitbit"] is False
