"""Random secret in a provider's webhook callback path.

For providers that do not sign their webhooks (or sign them with a key we cannot
get), the callback URL itself is the credential:
``{API_BASE_URL}/api/v1/providers/{provider}/webhooks/{callback_token}``. Only the
provider learns the URL, at subscription time, so a request that knows the token
came from the provider. ``BaseWebhookHandler.authenticate_callback`` checks it on
every request.

The token is a path segment, so it lands in access logs like any URL. Keep it out
of application logs, Sentry events and API responses with ``redact_callback_url``.
"""

import re
from secrets import compare_digest

from pydantic import SecretStr

from app.config import settings

#: Path parameter of the unified router's ``/{callback_token}`` routes.
CALLBACK_TOKEN_PARAM = "callback_token"

# The segment after /providers/{provider}/webhooks/, unless it is the management API.
# Stops at quotes and whitespace too, so a path inside a repr (b'/api/...') keeps its quote.
_TOKEN_SEGMENT = re.compile(r"(/providers/[^/?#'\"\s]+/webhooks/)(?!subscriptions(?:[/?#'\"\s]|$))[^/?#'\"\s]+")


def provider_webhook_url(provider: str) -> str:
    """The unified router's callback URL for ``provider``, without a token."""
    return f"{settings.api_base_url}{settings.api_v1}/providers/{provider}/webhooks"


def callback_url(provider: str, token: SecretStr | None) -> str | None:
    """The callback URL carrying ``token``, or ``None`` while the token is not configured."""
    if token is None or not token.get_secret_value():
        return None
    return f"{provider_webhook_url(provider)}/{token.get_secret_value()}"


def callback_token_matches(expected: SecretStr | None, provided: str | None) -> bool:
    """Constant-time check of a caller-supplied token; an unconfigured token matches nothing."""
    if expected is None or not expected.get_secret_value() or not provided:
        return False
    # compare_digest raises TypeError on non-ASCII str; the token is caller-supplied.
    return compare_digest(provided.encode("utf-8"), expected.get_secret_value().encode("utf-8"))


def redact_callback_url(url: str) -> str:
    """Replace the callback token in a URL or path with ``redacted``."""
    return _TOKEN_SEGMENT.sub(r"\1redacted", url)
