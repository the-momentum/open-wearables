from app.schemas.enums import ProviderName

SDK_PROVIDERS: frozenset[str] = frozenset(
    {
        ProviderName.APPLE.value,
        ProviderName.SAMSUNG.value,
        ProviderName.HEALTH_CONNECT.value,
    }
)

# Health Connect shipped as "google" before the provider split. Deployed app versions
# still send it, so the alias is permanent rather than a migration window.
SDK_PROVIDER_ALIASES: dict[str, str] = {"google": ProviderName.HEALTH_CONNECT.value}


def normalize_sdk_provider(raw: str | None) -> str | None:
    """Canonical slug for an SDK payload's ``provider``, or None if unsupported."""
    provider = SDK_PROVIDER_ALIASES.get(str(raw or "").lower(), str(raw or "").lower())
    return provider if provider in SDK_PROVIDERS else None
