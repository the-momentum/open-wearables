from app.schemas.enums import ProviderName

# Google's webhook subscriber endpoint predates the split and still points at /google/.
# Only that path is aliased: on the SDK endpoint "google" meant Health Connect instead.
_LEGACY_URL_SLUGS: dict[str, ProviderName] = {"google": ProviderName.GOOGLE_HEALTH}


def from_url_slug(slug: str) -> str:
    """Provider behind a path segment; takes a raw string since it runs on URL input."""
    legacy = _LEGACY_URL_SLUGS.get(slug)
    return legacy.value if legacy else slug
