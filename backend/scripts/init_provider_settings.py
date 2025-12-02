"""Initialize provider settings table with all available providers."""

from app.database import SessionLocal
from app.repositories.provider_settings_repository import ProviderSettingsRepository
from app.schemas import ProviderName


def init_provider_settings() -> None:
    """Ensure all providers from ProviderName enum exist in database."""
    with SessionLocal() as db:
        repo = ProviderSettingsRepository()
        all_providers = [provider.value for provider in ProviderName]
        repo.ensure_all_providers_exist(db, all_providers)
        print(f"✓ Provider settings initialized: {', '.join(all_providers)}")


if __name__ == "__main__":
    init_provider_settings()
