"""Which redirect_uri the OAuth flow may send a browser back to.

Without a check, the callback was an open redirect: any site could start a
provider sign-in on this instance and have the user land on a page of its choice.
"""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.config import settings

_WEB_SCHEMES = ("http", "https")


def _origin(url: str) -> str | None:
    parts = urlsplit(url.strip())
    if parts.scheme not in _WEB_SCHEMES or not parts.netloc:
        return None
    return f"{parts.scheme}://{parts.netloc}".lower()


def _allowed() -> tuple[set[str], set[str]]:
    """(web origins, exact app callbacks) currently allowed."""
    entries = [e.strip() for e in settings.oauth_redirect_allowlist.split(",") if e.strip()]
    entries += [settings.frontend_url, *(str(origin) for origin in settings.cors_origins)]
    origins = {origin for entry in entries if (origin := _origin(entry))}
    callbacks = {_without_query(entry) for entry in entries if _origin(entry) is None}
    return origins, callbacks


def _without_query(uri: str) -> str:
    parts = urlsplit(uri.strip())
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, "", ""))


def is_allowed_redirect(uri: str) -> bool:
    origins, callbacks = _allowed()
    try:
        parts = urlsplit(uri)
        if parts.scheme in _WEB_SCHEMES:
            return _origin(uri) in origins
        if not parts.scheme or parts.scheme in ("javascript", "data", "file", "vbscript"):
            return False
        return _without_query(uri) in callbacks
    except ValueError:
        return False


def with_result(uri: str, **params: str) -> str:
    """uri with the outcome added to its query, keeping what was there."""
    parts = urlsplit(uri)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k not in params]
    query += list(params.items())
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
