"""Bearer-token auth for the HTTP transport."""

import hmac

from fastmcp.server.auth import AccessToken, TokenVerifier

from app.config import settings


def secrets_match(supplied: str, expected: str) -> bool:
    """Compare two secrets in constant time; non-ASCII input is compared as UTF-8 instead of raising."""
    return hmac.compare_digest(supplied.encode(), expected.encode())


class SharedSecretVerifier(TokenVerifier):
    """Validates the MCP bearer token against a single shared secret."""

    def __init__(self) -> None:
        """Load the shared bearer token from settings."""
        super().__init__(required_scopes=None)
        self._token = settings.mcp_bearer_token.get_secret_value()

    async def verify_token(self, token: str) -> AccessToken | None:
        """Validate a bearer token against the configured shared secret."""
        if not self._token or not secrets_match(token, self._token):
            return None
        return AccessToken(token=token, client_id="open-wearables-mcp-client", scopes=[])
