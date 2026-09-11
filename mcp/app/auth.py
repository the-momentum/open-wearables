"""Bearer-token auth for the HTTP transport."""

import hmac

from fastmcp.server.auth import AccessToken, TokenVerifier

from app.config import settings


class SharedSecretVerifier(TokenVerifier):
    """Validates the MCP bearer token against a single shared secret."""

    def __init__(self) -> None:
        """Load the shared bearer token from settings."""
        super().__init__(required_scopes=None)
        self._token = settings.mcp_bearer_token.get_secret_value()

    async def verify_token(self, token: str) -> AccessToken | None:
        """Validate a bearer token against the configured shared secret."""
        if not self._token or not hmac.compare_digest(token, self._token):
            return None
        return AccessToken(token=token, client_id="open-wearables-mcp-client", scopes=[])
