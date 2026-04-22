"""Initialize provider settings table with all available providers."""

from app.database import SessionLocal
from app.repositories.provider_settings_repository import ProviderSettingsRepository
from app.schemas.auth import LiveSyncMode
from app.schemas.enums import ProviderName
from app.services.providers.base_strategy import ProviderCapabilities
from app.services.providers.factory import ProviderFactory


def _default_live_sync_mode(caps: ProviderCapabilities) -> LiveSyncMode | None:
    """Derive the default live_sync_mode from a provider's capabilities."""
    if caps.rest_pull:
        return LiveSyncMode.PULL
    if caps.client_sdk:
        return None
    if caps.webhook_callback or caps.webhook_ping or caps.webhook_stream:
        return LiveSyncMode.WEBHOOK
    return None


def init_provider_settings() -> None:
    """Ensure all providers exist and have correct live_sync_mode defaults."""
    factory = ProviderFactory()
    all_providers = [p.value for p in ProviderName if p.value not in ("unknown", "internal")]

    default_modes: dict[str, LiveSyncMode | None] = {}
    for provider in all_providers:
        try:
            caps = factory.get_provider(provider).capabilities
            default_modes[provider] = _default_live_sync_mode(caps)
        except ValueError:
            default_modes[provider] = None

    with SessionLocal() as db:
        repo = ProviderSettingsRepository()
        repo.ensure_all_providers_exist(db, all_providers, default_modes)
        print(f"✓ Provider settings initialized: {', '.join(all_providers)}")


if __name__ == "__main__":
    init_provider_settings()
