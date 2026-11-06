"""Print the callback URL to set for every data type in the Garmin portal.

Garmin does not sign its notifications, so Open Wearables accepts them only on a URL
that carries a secret token derived from SECRET_KEY. Garmin has no API for its endpoint
configuration: the operator pastes this URL by hand into
https://apis.garmin.com/tools/endpoints, for every data type. Run it where the backend
runs, so that it sees the same SECRET_KEY and API_BASE_URL:

    cd backend && uv run python scripts/garmin_webhook_url.py
    docker compose exec app uv run python scripts/garmin_webhook_url.py

The URL goes to stdout and the instructions to stderr, so `$(...)` captures the URL alone.
Treat the URL like a password. It changes with SECRET_KEY or API_BASE_URL; run the script
again after changing either and update every data type in the Garmin portal.
"""

import sys
from ipaddress import ip_address
from urllib.parse import urlsplit

from app.config import settings
from app.utils.webhook_callback import callback_url

PORTAL_URL = "https://apis.garmin.com/tools/endpoints"
_LOCAL_HOSTS = {"localhost", "host.docker.internal"}


def _not_public_ip(host: str) -> bool:
    try:
        return not ip_address(host).is_global
    except ValueError:  # a host name, not an IP
        return False


def _reachable_by_garmin(base_url: str) -> bool:
    """Garmin sends only to HTTPS on the standard port (Health API, Endpoint Configuration)."""
    base = urlsplit(base_url)
    host = base.hostname or ""
    try:
        port = base.port
    except ValueError:  # not a number
        return False
    return base.scheme == "https" and port in (None, 443) and host not in _LOCAL_HOSTS and not _not_public_ip(host)


def main() -> None:
    if not _reachable_by_garmin(settings.api_base_url):
        print(
            f"Warning: API_BASE_URL is {settings.api_base_url!r}. Garmin sends only to a public HTTPS URL on "
            "the standard port; run this where the backend runs, with its API_BASE_URL.",
            file=sys.stderr,
        )
    print(
        f"Set this URL for every data type in the Garmin portal ({PORTAL_URL}), "
        "Deregistrations and User Permissions included:",
        file=sys.stderr,
    )
    print(callback_url("garmin"))


if __name__ == "__main__":
    main()
