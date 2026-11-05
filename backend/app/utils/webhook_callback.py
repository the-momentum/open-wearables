import re
from secrets import compare_digest

from pydantic import SecretStr

from app.config import settings
from app.utils.config_utils import derive_secret

#: Path parameter of the unified router's ``/{callback_token}`` routes.
CALLBACK_TOKEN_PARAM = "callback_token"

# The segment after /providers/{provider}/webhooks/, unless it is the management API.
# Stops at quotes and whitespace too, so a path inside a repr (b'/api/...') keeps its quote.
_TOKEN_SEGMENT = re.compile(r"(/providers/[^/?#'\"\s]+/webhooks/)(?!subscriptions(?:[/?#'\"\s]|$))[^/?#'\"\s]+")


def provider_webhook_url(provider: str) -> str:
    """The unified router's callback URL for ``provider``, without a token."""
    return f"{settings.api_base_url}{settings.api_v1}/providers/{provider}/webhooks"


def callback_token(provider: str) -> SecretStr:
    """Secret in the callback path of a provider that cannot authenticate its webhooks otherwise."""
    return SecretStr(derive_secret(settings.secret_key, f"{provider}-webhook-callback-token"))


def callback_url(provider: str) -> str:
    return f"{provider_webhook_url(provider)}/{callback_token(provider).get_secret_value()}"


def callback_token_matches(expected: SecretStr | None, provided: str | None) -> bool:
    """Constant-time check of a caller-supplied token; an unconfigured token matches nothing."""
    if expected is None or not expected.get_secret_value() or not provided:
        return False
    # compare_digest raises TypeError on non-ASCII str; the token is caller-supplied.
    return compare_digest(provided.encode("utf-8"), expected.get_secret_value().encode("utf-8"))


def redact_callback_url(url: str) -> str:
    """Replace the callback token in a URL or path with ``redacted``; it lands in logs like any URL."""
    return _TOKEN_SEGMENT.sub(r"\1redacted", url)
