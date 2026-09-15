from app.schemas.enums import ProviderName

# The cloud path was reachable at /google/ before it became its own provider, and that
# path is baked into OAuth redirect URIs and Health API subscriber endpoints registered
# with Google. Those URLs keep resolving, but nothing publishes them any more: every URL
# this application emits uses the provider's own slug.
#
# Only the cloud path is aliased. On the SDK upload endpoint "google" meant Health Connect
# instead, so the legacy name is channel-ambiguous and must not be resolved outside the
# routes that only ever served one of the two.
_LEGACY_URL_SLUGS: dict[str, ProviderName] = {"google": ProviderName.GOOGLE_HEALTH}


def from_url_slug(slug: str) -> str:
    """Provider behind a path segment. Both the legacy and current slug resolve.

    Takes a plain string because it runs on untrusted URL input, before the value is
    known to name a provider at all; the caller validates what comes back.
    """
    legacy = _LEGACY_URL_SLUGS.get(slug)
    return legacy.value if legacy else slug
