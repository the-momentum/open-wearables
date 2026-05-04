from celery import current_app as celery_app

from app.config import settings
from app.database import DbSession
from app.repositories.provider_settings_repository import ProviderSettingsRepository
from app.schemas.auth.live_sync_mode import LiveSyncMode
from app.schemas.enums import ProviderName
from app.schemas.model_crud.data_priority import (
    ProviderSettingRead,
    ProviderSettingUpdate,
)
from app.services.providers.factory import ProviderFactory

_REGISTER_WEBHOOKS_TASK = "app.integrations.celery.tasks.register_provider_webhooks_task.register_provider_webhooks"


class ProviderSettingsService:
    """Service for managing provider configuration."""

    def __init__(self):
        self.factory = ProviderFactory()
        self.repo = ProviderSettingsRepository()

    def _to_read(self, provider_key: str, setting_map: dict) -> ProviderSettingRead:
        strategy = self.factory.get_provider(provider_key)
        setting = setting_map.get(provider_key)
        return ProviderSettingRead(
            provider=provider_key,
            name=strategy.display_name,
            has_cloud_api=strategy.has_cloud_api,
            is_enabled=setting.is_enabled if setting else True,
            icon_url=strategy.icon_url,
            live_sync_mode=(
                setting.live_sync_mode
                if (setting and setting.live_sync_mode is not None)
                else strategy.default_live_sync_mode
            ),
            live_sync_configurable=strategy.live_sync_configurable,
        )

    def get_all_providers(self, db: DbSession) -> list[ProviderSettingRead]:
        """Get all providers merged with their DB settings and strategy metadata."""
        db_settings_map = self.repo.get_all(db)
        return [self._to_read(p.value, db_settings_map) for p in ProviderName if p.value not in ("unknown", "internal")]

    def update_provider_setting(
        self,
        db: DbSession,
        provider: str,
        update: ProviderSettingUpdate,
    ) -> ProviderSettingRead:
        """Update is_enabled and/or live_sync_mode for a provider."""
        try:
            strategy = self.factory.get_provider(provider)
        except ValueError:
            raise ValueError(f"Unknown provider: {provider}")

        if update.live_sync_mode is not None and not strategy.live_sync_configurable:
            raise ValueError(f"Provider '{provider}' does not support live sync mode configuration")

        db_settings_map = self.repo.get_all(db)
        current = db_settings_map.get(provider)
        new_is_enabled = (
            update.is_enabled if update.is_enabled is not None else (current.is_enabled if current else True)
        )

        effective_live_sync_mode = update.live_sync_mode
        if effective_live_sync_mode is None and (current is None or current.live_sync_mode is None):
            effective_live_sync_mode = strategy.default_live_sync_mode

        setting = self.repo.upsert(db, provider, new_is_enabled, effective_live_sync_mode)

        if update.live_sync_mode == LiveSyncMode.WEBHOOK and strategy.capabilities.webhook_registration_api:
            callback_url = f"{settings.api_base_url}{settings.api_v1}/providers/{provider}/webhooks"
            celery_app.send_task(_REGISTER_WEBHOOKS_TASK, args=[provider, callback_url], queue="webhook_sync")

        return ProviderSettingRead(
            provider=provider,
            name=strategy.display_name,
            has_cloud_api=strategy.has_cloud_api,
            is_enabled=setting.is_enabled,
            icon_url=strategy.icon_url,
            live_sync_mode=(
                setting.live_sync_mode if setting.live_sync_mode is not None else strategy.default_live_sync_mode
            ),
            live_sync_configurable=strategy.live_sync_configurable,
        )

    def bulk_update_providers(self, db: DbSession, updates: dict[str, bool]) -> list[ProviderSettingRead]:
        """Bulk update is_enabled for multiple providers."""
        for provider in updates:
            try:
                self.factory.get_provider(provider)
            except ValueError:
                raise ValueError(f"Unknown provider: {provider}")

        self.repo.bulk_update(db, updates)
        return self.get_all_providers(db)
