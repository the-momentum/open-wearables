"""Initialize provider settings table with all available providers."""

from app.database import SessionLocal
from app.repositories.provider_settings_repository import ProviderSettingsRepository
from app.schemas.enums import ProviderName
from app.services.providers.factory import ProviderFactory


def init_provider_settings() -> None:
    """Ensure all providers exist and have correct live_sync_mode defaults."""
    factory = ProviderFactory()
    all_providers = [p.value for p in ProviderName if p.value not in ("unknown", "internal")]

    default_modes = {}
    for provider in all_providers:
        try:
            default_modes[provider] = factory.get_provider(provider).default_live_sync_mode
        except ValueError:
            default_modes[provider] = None

    with SessionLocal() as db:
        repo = ProviderSettingsRepository()
        repo.ensure_all_providers_exist(db, all_providers, default_modes)
        print(f"✓ Provider settings initialized: {', '.join(all_providers)}")


if __name__ == "__main__":
    init_provider_settings()
