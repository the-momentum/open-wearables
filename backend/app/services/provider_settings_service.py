from app.database import DbSession
from app.repositories.provider_settings_repository import ProviderSettingsRepository
from app.schemas import ProviderName, ProviderSettingRead, ProviderSettingUpdate
from app.services.providers.factory import ProviderFactory


class ProviderSettingsService:
    """Service for managing provider configuration."""

    def __init__(self):
        self.factory = ProviderFactory()
        self.repo = ProviderSettingsRepository()

    def get_all_providers(self, db: DbSession) -> list[ProviderSettingRead]:
        """
        Get all providers with their enabled status.
        Merges provider strategies with database settings.
        """
        # 1. Get settings from DB
        db_settings_map = self.repo.get_all(db)

        # 2. Merge with provider strategies
        result = []
        for provider_enum in ProviderName:
            provider_key = provider_enum.value
            # Skip providers without active strategies
            if provider_key in ("unknown", "oura"):
                continue
            strategy = self.factory.get_provider(provider_key)

            # Default enabled = True unless explicitly disabled in DB
            is_enabled = db_settings_map.get(provider_key, True)

            result.append(
                ProviderSettingRead(
                    provider=provider_key,
                    name=strategy.display_name,
                    has_cloud_api=strategy.has_cloud_api,
                    is_enabled=is_enabled,
                    icon_url=strategy.icon_url,
                ),
            )

        return result

    def update_provider_status(
        self,
        db: DbSession,
        provider: str,
        update: ProviderSettingUpdate,
    ) -> ProviderSettingRead:
        """Update provider enabled status."""
        # Validate provider exists
        try:
            strategy = self.factory.get_provider(provider)
        except ValueError:
            raise ValueError(f"Unknown provider: {provider}")

        # Update in DB
        setting = self.repo.upsert(db, provider, update.is_enabled)

        return ProviderSettingRead(
            provider=provider,
            name=strategy.display_name,
            has_cloud_api=strategy.has_cloud_api,
            is_enabled=setting.is_enabled,
            icon_url=strategy.icon_url,
        )

    def bulk_update_providers(self, db: DbSession, updates: dict[str, bool]) -> list[ProviderSettingRead]:
        """Bulk update provider settings. Validates all providers exist before updating."""
        # Validate all providers exist
        for provider in updates:
            try:
                self.factory.get_provider(provider)
            except ValueError:
                raise ValueError(f"Unknown provider: {provider}")

        # Perform bulk update
        self.repo.bulk_update(db, updates)

        # Return updated settings
        return self.get_all_providers(db)
