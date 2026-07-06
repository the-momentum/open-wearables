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
from app.schemas.auth import LiveSyncMode
from tests.factories import ProviderSettingFactory


class TestProviderSettingsRepository:
    """Test suite for ProviderSettingsRepository."""

    @pytest.fixture
    def provider_repo(self) -> ProviderSettingsRepository:
        """Create ProviderSettingsRepository instance."""
        return ProviderSettingsRepository()

    def test_get_all_empty_database(self, db: Session, provider_repo: ProviderSettingsRepository) -> None:
        """Test get_all returns empty dict when no settings exist."""
        result = provider_repo.get_all(db)
        assert result == {}

    def test_get_all_single_setting(self, db: Session, provider_repo: ProviderSettingsRepository) -> None:
        """Test get_all returns single provider setting."""
        ProviderSettingFactory(provider="garmin", is_enabled=True)

        result = provider_repo.get_all(db)

        assert len(result) == 1
        assert result["garmin"].is_enabled is True

    def test_get_all_multiple_settings(self, db: Session, provider_repo: ProviderSettingsRepository) -> None:
        """Test get_all returns multiple provider settings."""
        ProviderSettingFactory(provider="garmin", is_enabled=True)
        ProviderSettingFactory(provider="apple", is_enabled=False)
        ProviderSettingFactory(provider="fitbit", is_enabled=True)

        result = provider_repo.get_all(db)

        assert len(result) == 3
        assert result["garmin"].is_enabled is True
        assert result["apple"].is_enabled is False
        assert result["fitbit"].is_enabled is True

    def test_upsert_creates_new_provider(self, db: Session, provider_repo: ProviderSettingsRepository) -> None:
        """Test upsert creates a new provider setting when it doesn't exist."""
        result = provider_repo.upsert(db, provider="strava", is_enabled=True)

        assert result.provider == "strava"
        assert result.is_enabled is True

        db.expire_all()
        all_settings = provider_repo.get_all(db)
        assert "strava" in all_settings
        assert all_settings["strava"].is_enabled is True

    def test_upsert_updates_existing_provider(self, db: Session, provider_repo: ProviderSettingsRepository) -> None:
        """Test upsert updates an existing provider setting."""
        ProviderSettingFactory(provider="garmin", is_enabled=True)

        result = provider_repo.upsert(db, provider="garmin", is_enabled=False)

        assert result.provider == "garmin"
        assert result.is_enabled is False

        db.expire_all()
        all_settings = provider_repo.get_all(db)
        assert all_settings["garmin"].is_enabled is False

    def test_upsert_toggle_enabled_to_disabled(self, db: Session, provider_repo: ProviderSettingsRepository) -> None:
        """Test upsert can toggle a provider from enabled to disabled."""
        ProviderSettingFactory(provider="apple", is_enabled=True)

        result = provider_repo.upsert(db, provider="apple", is_enabled=False)

        assert result.is_enabled is False
        db.expire_all()
        assert provider_repo.get_all(db)["apple"].is_enabled is False

    def test_upsert_toggle_disabled_to_enabled(self, db: Session, provider_repo: ProviderSettingsRepository) -> None:
        """Test upsert can toggle a provider from disabled to enabled."""
        ProviderSettingFactory(provider="fitbit", is_enabled=False)

        result = provider_repo.upsert(db, provider="fitbit", is_enabled=True)

        assert result.is_enabled is True
        db.expire_all()
        assert provider_repo.get_all(db)["fitbit"].is_enabled is True

    def test_ensure_all_providers_exist_empty_database(
        self,
        db: Session,
        provider_repo: ProviderSettingsRepository,
    ) -> None:
        """Test ensure_all_providers_exist adds all providers when database is empty."""
        providers = ["garmin", "apple", "fitbit", "strava"]

        provider_repo.ensure_all_providers_exist(db, providers, {})

        db.expire_all()
        all_settings = provider_repo.get_all(db)
        assert len(all_settings) == 4
        for provider in providers:
            assert provider in all_settings
            assert all_settings[provider].is_enabled is True

    def test_ensure_all_providers_exist_partial_existing(
        self,
        db: Session,
        provider_repo: ProviderSettingsRepository,
    ) -> None:
        """Test ensure_all_providers_exist adds only missing providers."""
        ProviderSettingFactory(provider="garmin", is_enabled=False)
        ProviderSettingFactory(provider="apple", is_enabled=True)
        providers = ["garmin", "apple", "fitbit", "strava"]

        provider_repo.ensure_all_providers_exist(db, providers, {})

        db.expire_all()
        all_settings = provider_repo.get_all(db)
        assert len(all_settings) == 4
        assert all_settings["garmin"].is_enabled is False
        assert all_settings["apple"].is_enabled is True
        assert all_settings["fitbit"].is_enabled is True
        assert all_settings["strava"].is_enabled is True

    def test_ensure_all_providers_exist_all_existing(
        self,
        db: Session,
        provider_repo: ProviderSettingsRepository,
    ) -> None:
        """Test ensure_all_providers_exist does nothing when all providers exist."""
        ProviderSettingFactory(provider="garmin", is_enabled=False)
        ProviderSettingFactory(provider="apple", is_enabled=True)
        providers = ["garmin", "apple"]

        provider_repo.ensure_all_providers_exist(db, providers, {})

        db.expire_all()
        all_settings = provider_repo.get_all(db)
        assert len(all_settings) == 2
        assert all_settings["garmin"].is_enabled is False
        assert all_settings["apple"].is_enabled is True

    def test_bulk_update_multiple_providers(self, db: Session, provider_repo: ProviderSettingsRepository) -> None:
        """Test bulk_update updates multiple providers at once."""
        ProviderSettingFactory(provider="garmin", is_enabled=True)
        ProviderSettingFactory(provider="apple", is_enabled=True)

        updates = {"garmin": False, "apple": False, "fitbit": True}
        provider_repo.bulk_update(db, updates)

        db.expire_all()
        all_settings = provider_repo.get_all(db)
        assert all_settings["garmin"].is_enabled is False
        assert all_settings["apple"].is_enabled is False
        assert all_settings["fitbit"].is_enabled is True

    def test_bulk_update_mixed_insert_and_update(self, db: Session, provider_repo: ProviderSettingsRepository) -> None:
        """Test bulk_update can both insert new providers and update existing ones."""
        ProviderSettingFactory(provider="garmin", is_enabled=True)

        updates = {"garmin": False, "strava": True, "fitbit": False}
        provider_repo.bulk_update(db, updates)

        db.expire_all()
        all_settings = provider_repo.get_all(db)
        assert len(all_settings) == 3
        assert all_settings["garmin"].is_enabled is False
        assert all_settings["strava"].is_enabled is True
        assert all_settings["fitbit"].is_enabled is False

    def test_upsert_persists_live_sync_mode(self, db: Session, provider_repo: ProviderSettingsRepository) -> None:
        """Test upsert stores live_sync_mode and it survives a cache expiry."""
        result = provider_repo.upsert(db, provider="strava", is_enabled=True, live_sync_mode=LiveSyncMode.PULL)

        assert result.live_sync_mode == LiveSyncMode.PULL

        db.expire_all()
        assert provider_repo.get_all(db)["strava"].live_sync_mode == LiveSyncMode.PULL

    def test_ensure_all_providers_exist_backfills_live_sync_mode(
        self,
        db: Session,
        provider_repo: ProviderSettingsRepository,
    ) -> None:
        """Test ensure_all_providers_exist backfills NULL live_sync_mode with the provided default."""
        # Insert a row with NULL live_sync_mode
        ProviderSettingFactory(provider="strava", is_enabled=True, live_sync_mode=None)

        provider_repo.ensure_all_providers_exist(db, ["strava"], {"strava": LiveSyncMode.PULL})

        db.expire_all()
        assert provider_repo.get_all(db)["strava"].live_sync_mode == LiveSyncMode.PULL
