from contextlib import suppress
from functools import lru_cache

from app.schemas.enums import ProviderName

# Health Connect shipped as "google" before the provider split. Deployed app versions
# still send it, so the alias is permanent rather than a migration window.
SDK_PROVIDER_ALIASES: dict[str, str] = {"google": ProviderName.HEALTH_CONNECT.value}


@lru_cache(maxsize=1)
def sdk_providers() -> frozenset[str]:
    """Providers the mobile SDK can feed, taken from each strategy's own capabilities."""
    from app.services.providers.factory import ProviderFactory

    factory = ProviderFactory()
    names: set[str] = set()
    for provider in ProviderName:
        with suppress(ValueError):  # sentinel members have no strategy
            if factory.get_provider(provider.value).capabilities.client_sdk:
                names.add(provider.value)
    return frozenset(names)


def normalize_sdk_provider(raw: str | None) -> str | None:
    """Canonical slug for an SDK payload's ``provider``, or None if unsupported."""
    provider = str(raw or "").lower()
    provider = SDK_PROVIDER_ALIASES.get(provider, provider)
    return provider if provider in sdk_providers() else None
