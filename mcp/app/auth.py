"""OAuth 2.1 authentication for HTTP transport.

Implements the MCP authorization spec so Claude Desktop (Connectors UI) and other
MCP clients can authenticate using an Open Wearables API key from the developer panel.

Flow:
1. Claude discovers OAuth metadata at /.well-known/oauth-authorization-server
2. Claude registers as a client via Dynamic Client Registration (/register)
3. Claude redirects the user to /authorize
4. We redirect to /enter-api-key - a form where the user pastes their API key
5. We validate the key against the backend, create an auth code, redirect back to Claude
6. Claude exchanges the code for an access token at /token
7. All subsequent MCP requests include Authorization: Bearer <access-token>
8. Tools read the API key from the token claims and use it for backend requests
"""

import logging
import secrets
import time
from typing import Any

import httpx
from fastmcp.server.auth.providers.in_memory import (
    DEFAULT_ACCESS_TOKEN_EXPIRY_SECONDS,
    InMemoryOAuthProvider,
)
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    AuthorizeError,
    RefreshToken,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse
from starlette.routing import Route

from app.config import settings

logger = logging.getLogger(__name__)

# Token expiry
_ACCESS_TOKEN_TTL = DEFAULT_ACCESS_TOKEN_EXPIRY_SECONDS  # 1 hour
_REFRESH_TOKEN_TTL = 30 * 24 * 60 * 60  # 30 days
_PENDING_AUTH_TTL = 600  # 10 minutes


def _create_html_response(html: str, status_code: int = 200) -> HTMLResponse:
    return HTMLResponse(content=html, status_code=status_code)


class ApiKeyOAuthProvider(InMemoryOAuthProvider):
    """OAuth 2.1 provider that authenticates users via Open Wearables API keys.

    Extends InMemoryOAuthProvider with:
    - A custom /enter-api-key page where users paste their API key
    - Backend validation of API keys
    - API key propagation to access tokens via claims
    """

    def __init__(self, base_url: str) -> None:
        from fastmcp.server.auth.auth import ClientRegistrationOptions

        super().__init__(
            base_url=base_url,
            client_registration_options=ClientRegistrationOptions(enabled=True),
        )
        self._backend_url = settings.open_wearables_api_url.rstrip("/")
        self._timeout = settings.request_timeout
        # Pending auth requests: txn_id -> AuthorizationParams data
        self._pending_auths: dict[str, dict[str, Any]] = {}
        # Auth code -> API key mapping
        self._code_to_api_key: dict[str, str] = {}
        # Access/refresh token -> API key mapping
        self._token_to_api_key: dict[str, str] = {}

    async def authorize(
        self,
        client: OAuthClientInformationFull,
        params: AuthorizationParams,
    ) -> str:
        """Redirect to API key entry form instead of auto-approving."""
        if client.client_id is None:
            raise AuthorizeError(error="invalid_client", error_description="Client ID is required")
        if client.client_id not in self.clients:
            raise AuthorizeError(
                error="unauthorized_client",
                error_description=f"Client '{client.client_id}' not registered.",
            )

        txn_id = secrets.token_urlsafe(32)
        self._pending_auths[txn_id] = {
            "client_id": client.client_id,
            "redirect_uri": str(params.redirect_uri),
            "state": params.state,
            "scopes": params.scopes or [],
            "code_challenge": params.code_challenge,
            "redirect_uri_provided_explicitly": params.redirect_uri_provided_explicitly,
            "created_at": time.time(),
        }

        return f"{str(self.base_url).rstrip('/')}/enter-api-key?txn_id={txn_id}"

    async def exchange_authorization_code(
        self,
        client: OAuthClientInformationFull,
        authorization_code: AuthorizationCode,
    ) -> OAuthToken:
        """Exchange auth code for tokens, embedding the API key in token claims."""
        api_key = self._code_to_api_key.pop(authorization_code.code, None)

        # Create tokens via parent
        oauth_token = await super().exchange_authorization_code(client, authorization_code)

        # Patch the stored access token to include the API key in claims
        if api_key and oauth_token.access_token in self.access_tokens:
            old_token = self.access_tokens[oauth_token.access_token]
            self.access_tokens[oauth_token.access_token] = AccessToken(
                token=old_token.token,
                client_id=old_token.client_id,
                scopes=old_token.scopes,
                expires_at=old_token.expires_at,
                claims={"api_key": api_key},
            )
            # Track for refresh token rotation
            self._token_to_api_key[oauth_token.access_token] = api_key
            if oauth_token.refresh_token:
                self._token_to_api_key[oauth_token.refresh_token] = api_key

        return oauth_token

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        """Refresh tokens, propagating the API key to the new access token."""
        api_key = self._token_to_api_key.get(refresh_token.token)

        oauth_token = await super().exchange_refresh_token(client, refresh_token, scopes)

        if api_key and oauth_token.access_token in self.access_tokens:
            old_token = self.access_tokens[oauth_token.access_token]
            self.access_tokens[oauth_token.access_token] = AccessToken(
                token=old_token.token,
                client_id=old_token.client_id,
                scopes=old_token.scopes,
                expires_at=old_token.expires_at,
                claims={"api_key": api_key},
            )
            self._token_to_api_key[oauth_token.access_token] = api_key
            if oauth_token.refresh_token:
                self._token_to_api_key[oauth_token.refresh_token] = api_key

        # Clean up old token mapping
        self._token_to_api_key.pop(refresh_token.token, None)

        return oauth_token

    # --- Custom routes ---

    def get_routes(self, mcp_path: str | None = None) -> list[Route]:
        """Add API key form route to standard OAuth routes."""
        routes = super().get_routes(mcp_path)
        routes.append(
            Route("/enter-api-key", endpoint=self._handle_api_key_page, methods=["GET", "POST"]),
        )
        return routes

    async def _handle_api_key_page(self, request: Request) -> HTMLResponse | RedirectResponse:
        """Handle the API key entry form."""
        if request.method == "POST":
            return await self._submit_api_key(request)
        return await self._show_api_key_form(request)

    async def _show_api_key_form(self, request: Request) -> HTMLResponse:
        """Render the API key entry form."""
        txn_id = request.query_params.get("txn_id", "")

        pending = self._pending_auths.get(txn_id)
        if not pending or (time.time() - pending["created_at"]) > _PENDING_AUTH_TTL:
            self._pending_auths.pop(txn_id, None)
            return _create_html_response(
                _error_html("Invalid or expired request", "Please try connecting again from your AI assistant."),
                status_code=400,
            )

        return _create_html_response(_api_key_form_html(txn_id))

    async def _submit_api_key(self, request: Request) -> HTMLResponse | RedirectResponse:
        """Validate the API key and complete the OAuth flow."""
        form = await request.form()
        txn_id = str(form.get("txn_id", ""))
        api_key = str(form.get("api_key", "")).strip()

        pending = self._pending_auths.pop(txn_id, None)
        if not pending:
            return _create_html_response(
                _error_html("Invalid or expired request", "Please try connecting again."),
                status_code=400,
            )

        if not api_key:
            # Re-show form with error
            self._pending_auths[txn_id] = pending
            return _create_html_response(_api_key_form_html(txn_id, error="Please enter your API key."))

        # Validate API key against backend
        valid = await self._validate_api_key(api_key)
        if not valid:
            self._pending_auths[txn_id] = pending
            return _create_html_response(
                _api_key_form_html(txn_id, error="Invalid API key. Please check and try again."),
            )

        # Create authorization code
        code_value = f"ow_auth_{secrets.token_hex(16)}"
        auth_code = AuthorizationCode(
            code=code_value,
            client_id=pending["client_id"],
            redirect_uri=pending["redirect_uri"],
            redirect_uri_provided_explicitly=pending["redirect_uri_provided_explicitly"],
            scopes=pending["scopes"],
            expires_at=time.time() + 300,
            code_challenge=pending["code_challenge"],
        )
        self.auth_codes[code_value] = auth_code
        self._code_to_api_key[code_value] = api_key

        redirect_url = construct_redirect_uri(
            pending["redirect_uri"],
            code=code_value,
            state=pending["state"],
        )
        return RedirectResponse(url=redirect_url, status_code=302)

    async def _validate_api_key(self, api_key: str) -> bool:
        """Validate an API key by calling the backend."""
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as http:
                response = await http.get(
                    f"{self._backend_url}/api/v1/users",
                    params={"limit": 1},
                    headers={"X-Open-Wearables-API-Key": api_key},
                )
            return response.status_code == 200
        except httpx.HTTPError as e:
            logger.error(f"Backend unreachable during API key validation: {e}")
            return False


# --- HTML templates ---


def _api_key_form_html(txn_id: str, error: str | None = None) -> str:
    error_block = f'<div class="error">{error}</div>' if error else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Connect to Open Wearables</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               background: #0a0a0a; color: #e5e5e5; min-height: 100vh;
               display: flex; align-items: center; justify-content: center; }}
        .card {{ background: #171717; border: 1px solid #262626; border-radius: 12px;
                padding: 2rem; max-width: 420px; width: 100%; margin: 1rem; }}
        h1 {{ font-size: 1.25rem; font-weight: 600; margin-bottom: 0.25rem; }}
        .subtitle {{ color: #a3a3a3; font-size: 0.875rem; margin-bottom: 1.5rem; }}
        label {{ display: block; font-size: 0.875rem; font-weight: 500; margin-bottom: 0.5rem; }}
        input[type="text"] {{ width: 100%; padding: 0.625rem 0.75rem; background: #0a0a0a;
               border: 1px solid #333; border-radius: 8px; color: #e5e5e5;
               font-size: 0.875rem; outline: none; }}
        input[type="text"]:focus {{ border-color: #3b82f6; }}
        .hint {{ font-size: 0.75rem; color: #737373; margin-top: 0.375rem; }}
        button {{ width: 100%; padding: 0.625rem; background: #3b82f6; color: white;
                border: none; border-radius: 8px; font-size: 0.875rem; font-weight: 500;
                cursor: pointer; margin-top: 1.25rem; }}
        button:hover {{ background: #2563eb; }}
        .error {{ background: #3b1111; border: 1px solid #7f1d1d; color: #fca5a5;
                 padding: 0.625rem; border-radius: 8px; font-size: 0.8125rem; margin-bottom: 1rem; }}
    </style>
</head>
<body>
    <div class="card">
        <h1>Connect to Open Wearables</h1>
        <p class="subtitle">Enter your API key to give your AI assistant access to your health data.</p>
        {error_block}
        <form method="POST">
            <input type="hidden" name="txn_id" value="{txn_id}">
            <label for="api_key">API Key</label>
            <input type="text" id="api_key" name="api_key" placeholder="ow_..." autocomplete="off" autofocus>
            <p class="hint">Find your API key in the Open Wearables developer panel.</p>
            <button type="submit">Connect</button>
        </form>
    </div>
</body>
</html>"""


def _error_html(title: str, message: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               background: #0a0a0a; color: #e5e5e5; min-height: 100vh;
               display: flex; align-items: center; justify-content: center; }}
        .card {{ background: #171717; border: 1px solid #262626; border-radius: 12px;
                padding: 2rem; max-width: 420px; width: 100%; margin: 1rem; text-align: center; }}
        h1 {{ font-size: 1.25rem; margin-bottom: 0.5rem; }}
        p {{ color: #a3a3a3; font-size: 0.875rem; }}
    </style>
</head>
<body>
    <div class="card">
        <h1>{title}</h1>
        <p>{message}</p>
    </div>
</body>
</html>"""
