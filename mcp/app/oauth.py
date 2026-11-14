"""Self-contained OAuth 2.1 authorization server, gated by a single password.

Registered clients and access/refresh tokens are persisted to `state_file`
(when set) so connected clients stay authorized across restarts. Short-lived
state (pending logins, authorization codes, login rate limits) stays in memory.
"""

import html
import json
import logging
import os
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastmcp.server.auth.auth import AccessToken, ClientRegistrationOptions, OAuthProvider, RevocationOptions
from fastmcp.utilities.ui import INFO_BOX_STYLES, create_page, create_secure_html_response
from mcp.server.auth.provider import (
    AuthorizationCode,
    AuthorizationParams,
    AuthorizeError,
    RefreshToken,
    RegistrationError,
    TokenError,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from pydantic import AnyHttpUrl
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response
from starlette.routing import Route

from app.auth import secrets_match
from app.config import settings

logger = logging.getLogger(__name__)

# RFC 8707 error for an unknown resource. Older SDK versions leave it out of AuthorizeError's Literal.
_INVALID_TARGET: Any = "invalid_target"


AUTH_CODE_EXPIRY_SECONDS = 5 * 60
PENDING_AUTH_EXPIRY_SECONDS = 10 * 60
ACCESS_TOKEN_EXPIRY_SECONDS = 30 * 24 * 60 * 60

# A wrong password can't be retried more than this many times against a given
# authorization attempt before the client has to restart the OAuth flow ...
LOGIN_MAX_ATTEMPTS_PER_TXN = 5
# ... nor more than this many times from a given address within the window,
# which also bounds guessing across freshly-started authorization attempts.
LOGIN_RATE_LIMIT_WINDOW_SECONDS = 5 * 60
LOGIN_RATE_LIMIT_MAX_ATTEMPTS = 10

# Dynamic client registration (RFC 7591) is unauthenticated by design, so cap
# how many clients it can create to bound memory growth from abuse.
MAX_REGISTERED_CLIENTS = 100
# Every /authorize call stores a pending login until it expires, and it needs no password, so bound
# how many can wait at once overall and per client.
MAX_PENDING_AUTHORIZATIONS = 200
MAX_PENDING_AUTHORIZATIONS_PER_CLIENT = 10
# A registered client that never completes an authorization is dropped after this
# long, so unauthenticated registrations cannot fill the cap for good.
UNUSED_CLIENT_EXPIRY_SECONDS = 60 * 60


@dataclass
class _PendingAuthorization:
    """An in-flight `/authorize` request, waiting on the login form."""

    client: OAuthClientInformationFull
    params: AuthorizationParams
    expires_at: float
    attempts: int = 0


class SinglePasswordOAuthProvider(OAuthProvider):
    """OAuth authorization server backed by one shared password.

    Doesn't reuse fastmcp's InMemoryOAuthProvider: that one is documented as a
    testing double, and it doesn't track the resource/audience restriction
    (see _issue_tokens below) that this server needs to enforce.
    """

    def __init__(
        self,
        *,
        base_url: AnyHttpUrl | str,
        client_registration_options: ClientRegistrationOptions | None = None,
        revocation_options: RevocationOptions | None = None,
        state_file: str | Path | None = None,
    ) -> None:
        """Initialize client/token/authorization-code storage, restoring persisted state if any."""
        super().__init__(
            base_url=base_url,
            client_registration_options=client_registration_options,
            revocation_options=revocation_options,
        )
        self.clients: dict[str, OAuthClientInformationFull] = {}
        self.auth_codes: dict[str, AuthorizationCode] = {}
        self.access_tokens: dict[str, AccessToken] = {}
        self.refresh_tokens: dict[str, RefreshToken] = {}
        self._access_to_refresh: dict[str, str] = {}
        self._refresh_to_access: dict[str, str] = {}
        # RefreshToken (unlike AccessToken/AuthorizationCode) has no `resource`
        # field, so the RFC 8707 resource indicator is tracked here instead.
        self._refresh_resource: dict[str, str | None] = {}
        self._pending: dict[str, _PendingAuthorization] = {}
        self._failed_logins_by_ip: dict[str, list[float]] = {}
        self._state_file = Path(state_file) if state_file else None
        self._load_state()

    # --- Persistence ---
    def _load_state(self) -> None:
        """Restore clients and tokens from the state file; start empty if it is missing or unreadable."""
        if self._state_file is None or not self._state_file.exists():
            return
        try:
            data = json.loads(self._state_file.read_text())
            self.clients = {k: OAuthClientInformationFull.model_validate(v) for k, v in data["clients"].items()}
            self.access_tokens = {k: AccessToken.model_validate(v) for k, v in data["access_tokens"].items()}
            self.refresh_tokens = {k: RefreshToken.model_validate(v) for k, v in data["refresh_tokens"].items()}
            self._access_to_refresh = data["access_to_refresh"]
            self._refresh_to_access = data["refresh_to_access"]
            self._refresh_resource = data["refresh_resource"]
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            # Keep the unreadable file: starting empty and saving would otherwise overwrite it for good.
            corrupt = self._state_file.with_name(self._state_file.name + ".corrupt")
            logger.warning(
                "Could not read OAuth state from %s, moving it to %s and starting empty",
                self._state_file,
                corrupt,
                exc_info=True,
            )
            try:
                os.replace(self._state_file, corrupt)
            except OSError:
                logger.warning("Could not move the unreadable OAuth state aside", exc_info=True)
            self.clients, self.access_tokens, self.refresh_tokens = {}, {}, {}
            self._access_to_refresh, self._refresh_to_access, self._refresh_resource = {}, {}, {}

    def _save_state(self) -> None:
        """Atomically write clients and tokens to the state file (owner-only permissions).

        Raises OSError when it cannot be written, so a token operation is not reported as done
        (a revocation, say) while the file on disk still holds the old state.
        """
        if self._state_file is None:
            return
        data = {
            "clients": {k: v.model_dump(mode="json") for k, v in self.clients.items()},
            "access_tokens": {k: v.model_dump(mode="json") for k, v in self.access_tokens.items()},
            "refresh_tokens": {k: v.model_dump(mode="json") for k, v in self.refresh_tokens.items()},
            "access_to_refresh": self._access_to_refresh,
            "refresh_to_access": self._refresh_to_access,
            "refresh_resource": self._refresh_resource,
        }
        tmp = self._state_file.with_name(self._state_file.name + ".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self._state_file)

    def _token_state(self) -> tuple[dict, ...]:
        """Copy of the token tables, to roll back a multi-step change that fails to save."""
        return (
            dict(self.access_tokens),
            dict(self.refresh_tokens),
            dict(self._access_to_refresh),
            dict(self._refresh_to_access),
            dict(self._refresh_resource),
        )

    def _restore_token_state(self, state: tuple[dict, ...]) -> None:
        """Put the token tables back as `_token_state` captured them."""
        (
            self.access_tokens,
            self.refresh_tokens,
            self._access_to_refresh,
            self._refresh_to_access,
            self._refresh_resource,
        ) = state

    def _save_state_best_effort(self) -> None:
        """Persist after housekeeping that need not be durable: an expired entry is dead either way."""
        try:
            self._save_state()
        except OSError:
            logger.warning("Could not write OAuth state to %s", self._state_file, exc_info=True)

    # --- Dynamic client registration (RFC 7591) ---
    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        """Look up a previously registered client by ID."""
        return self.clients.get(client_id)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        """Register a new OAuth client, bounded by MAX_REGISTERED_CLIENTS."""
        if client_info.client_id is None:
            raise RegistrationError(error="invalid_client_metadata", error_description="client_id is required")
        self._gc()
        if len(self.clients) >= MAX_REGISTERED_CLIENTS:
            raise RegistrationError(
                error="invalid_client_metadata",
                error_description="Server has reached its maximum number of registered OAuth clients.",
            )
        self.clients[client_info.client_id] = client_info
        self._save_state()

    # --- Authorization: hand off to our own login page ---
    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        """Start an authorization attempt and return the login page URL."""
        if not self._resource_matches(params.resource):
            raise AuthorizeError(error=_INVALID_TARGET, error_description="Unknown resource.")
        self._gc()
        if client.client_id not in self.clients:
            raise AuthorizeError(error="unauthorized_client", error_description="Client registration expired.")
        waiting_for_client = sum(1 for p in self._pending.values() if p.client.client_id == client.client_id)
        if (
            len(self._pending) >= MAX_PENDING_AUTHORIZATIONS
            or waiting_for_client >= MAX_PENDING_AUTHORIZATIONS_PER_CLIENT
        ):
            raise AuthorizeError(error="temporarily_unavailable", error_description="Too many pending authorizations.")
        txn = secrets.token_urlsafe(24)
        self._pending[txn] = _PendingAuthorization(
            client=client,
            params=params,
            expires_at=time.time() + PENDING_AUTH_EXPIRY_SECONDS,
        )
        base = str(self.base_url).rstrip("/")
        return f"{base}/login?txn={txn}"

    def _resource_matches(self, resource: str | None) -> bool:
        """RFC 8707: a request or token that names a resource must name this server's MCP endpoint."""
        return not resource or str(resource).rstrip("/") == f"{str(self.base_url).rstrip('/')}/mcp"

    def _gc(self) -> None:
        """Sweep expired pending authorizations, access tokens and unused clients.

        Bounds memory growth for a long-running, unattended server. Refresh
        tokens have no expiry by design (a personal deployment is expected to
        stay connected), so those are only removed via explicit revocation or
        rotation, and clients that still hold one are kept.
        """
        now = time.time()
        for txn in [k for k, v in self._pending.items() if v.expires_at < now]:
            del self._pending[txn]
        for code in [k for k, v in self.auth_codes.items() if v.expires_at < now]:
            del self.auth_codes[code]
        expired = [t for t, a in self.access_tokens.items() if a.expires_at is not None and a.expires_at < now]
        for token in expired:
            self._expire_access(token)
        stale_clients = self._unused_client_ids(now)
        for client_id in stale_clients:
            del self.clients[client_id]
        for txn in [k for k, v in self._pending.items() if v.client.client_id in stale_clients]:
            del self._pending[txn]
        if expired or stale_clients:
            self._save_state_best_effort()
        for ip in list(self._failed_logins_by_ip):
            attempts = self._recent_failures(ip)
            if attempts:
                self._failed_logins_by_ip[ip] = attempts
            else:
                del self._failed_logins_by_ip[ip]

    @staticmethod
    def _client_ip(request: Request) -> str:
        """Address used to rate limit logins: the configured proxy header if present, else the socket peer."""
        header = settings.mcp_client_ip_header
        if header and (value := request.headers.get(header)):
            # With a list (X-Forwarded-For) the last entry is the one the nearest proxy appended.
            return value.split(",")[-1].strip()
        return request.client.host if request.client else "unknown"

    def _unused_client_ids(self, now: float) -> list[str]:
        """Clients registered long ago that hold no token and no unexpired authorization code.

        A pending login does not keep a client alive: it needs no password, so counting it would let anyone
        stop registered clients from ever expiring by starting an authorization for each.
        """
        in_use: set[str | None] = {t.client_id for t in self.access_tokens.values()}
        in_use |= {t.client_id for t in self.refresh_tokens.values()}
        in_use |= {c.client_id for c in self.auth_codes.values()}
        cutoff = now - UNUSED_CLIENT_EXPIRY_SECONDS
        return [
            client_id
            for client_id, client in self.clients.items()
            if client_id not in in_use and (client.client_id_issued_at or 0) < cutoff
        ]

    def _recent_failures(self, client_ip: str) -> list[float]:
        """Failed login timestamps from an address that are still inside the rate limit window."""
        cutoff = time.time() - LOGIN_RATE_LIMIT_WINDOW_SECONDS
        return [t for t in self._failed_logins_by_ip.get(client_ip, []) if t > cutoff]

    def _record_failed_login(self, client_ip: str) -> None:
        """Record a failed login attempt from an address for rate limiting."""
        self._failed_logins_by_ip[client_ip] = [*self._recent_failures(client_ip), time.time()]

    def _is_login_rate_limited(self, client_ip: str) -> bool:
        """Check whether an address has too many recent failed login attempts."""
        return len(self._recent_failures(client_ip)) >= LOGIN_RATE_LIMIT_MAX_ATTEMPTS

    def _render_login(
        self,
        txn: str,
        client: OAuthClientInformationFull,
        redirect_uri: str,
        error: str | None = None,
    ) -> str:
        """Render the password login page for a pending authorization."""
        error_box = f'<div class="info-box error"><p>{html.escape(error)}</p></div>' if error else ""
        client_name = html.escape(client.client_name or client.client_id or "An application")
        content = f"""
            <div class="container">
                <h1>Sign in to Open Wearables</h1>
                <p><strong>{client_name}</strong> wants to access your wearable health data.
                   It will be redirected to <code>{html.escape(redirect_uri)}</code> once you sign in.</p>
                {error_box}
                <form method="post" action="{html.escape(str(self.base_url).rstrip("/"))}/login">
                    <input type="hidden" name="txn" value="{html.escape(txn)}">
                    <input type="password" name="password" placeholder="Password" autofocus required
                           style="width:100%;padding:.6rem;margin:1rem 0;border:1px solid #e5e7eb;
                                  border-radius:.5rem;box-sizing:border-box;">
                    <button type="submit"
                            style="width:100%;padding:.6rem;border:0;border-radius:.5rem;
                                   background:#0a0a0a;color:#fff;font-weight:600;cursor:pointer;">
                        Authorize
                    </button>
                </form>
            </div>
        """
        return create_page(content=content, title="Sign in", additional_styles=INFO_BOX_STYLES)

    @staticmethod
    def _expired_response() -> HTMLResponse:
        """Page shown when a login transaction is unknown or has expired."""
        return create_secure_html_response(
            create_page(
                content='<div class="container"><h1>Authorization request expired</h1>'
                "<p>Please reconnect from your MCP client.</p></div>",
                title="Expired",
            ),
            status_code=400,
        )

    async def _handle_login_get(self, request: Request) -> HTMLResponse:
        """Serve the login page for a pending authorization transaction."""
        txn = request.query_params.get("txn", "")
        pending = self._pending.get(txn)
        if pending is None or pending.expires_at < time.time():
            return self._expired_response()
        error = request.query_params.get("error")
        login_page = self._render_login(txn, pending.client, str(pending.params.redirect_uri), error)
        return create_secure_html_response(login_page)

    async def _handle_login_post(self, request: Request) -> Response:
        """Validate the submitted password and issue an authorization code."""
        form = await request.form()
        txn = str(form.get("txn", ""))
        password = str(form.get("password", ""))
        pending = self._pending.get(txn)
        if pending is None or pending.expires_at < time.time():
            return self._expired_response()

        client_ip = self._client_ip(request)
        base = str(self.base_url).rstrip("/")
        if self._is_login_rate_limited(client_ip) or pending.attempts >= LOGIN_MAX_ATTEMPTS_PER_TXN:
            return create_secure_html_response(
                create_page(
                    content='<div class="container"><h1>Too many attempts</h1>'
                    "<p>Please wait and reconnect from your MCP client.</p></div>",
                    title="Too many attempts",
                ),
                status_code=429,
            )

        expected = settings.mcp_oauth_password.get_secret_value()
        if not expected or not secrets_match(password, expected):
            pending.attempts += 1
            self._record_failed_login(client_ip)
            return RedirectResponse(f"{base}/login?txn={txn}&error=Incorrect+password", status_code=303)

        del self._pending[txn]
        client, params = pending.client, pending.params
        if client.client_id is None:
            return self._expired_response()

        code_value = secrets.token_hex(32)
        self.auth_codes[code_value] = AuthorizationCode(
            code=code_value,
            client_id=client.client_id,
            redirect_uri=params.redirect_uri,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
            scopes=params.scopes or [],
            expires_at=time.time() + AUTH_CODE_EXPIRY_SECONDS,
            code_challenge=params.code_challenge,
            resource=params.resource,
        )
        redirect_uri = construct_redirect_uri(str(params.redirect_uri), code=code_value, state=params.state)
        return RedirectResponse(redirect_uri, status_code=303)

    def get_routes(self, mcp_path: str | None = None) -> list[Route]:
        """Add the login page routes to the standard OAuth server routes."""
        routes = super().get_routes(mcp_path)
        routes.append(Route("/login", endpoint=self._handle_login_get, methods=["GET"]))
        routes.append(Route("/login", endpoint=self._handle_login_post, methods=["POST"]))
        return routes

    # --- Codes / tokens ---
    async def load_authorization_code(
        self,
        client: OAuthClientInformationFull,
        authorization_code: str,
    ) -> AuthorizationCode | None:
        """Look up a still-valid authorization code issued to this client."""
        code = self.auth_codes.get(authorization_code)
        if code is None:
            return None
        if code.client_id != client.client_id or code.expires_at < time.time():
            self.auth_codes.pop(authorization_code, None)
            return None
        return code

    async def exchange_authorization_code(
        self,
        client: OAuthClientInformationFull,
        authorization_code: AuthorizationCode,
    ) -> OAuthToken:
        """Redeem a one-time authorization code for an access/refresh token pair."""
        if authorization_code.code not in self.auth_codes:
            raise TokenError("invalid_grant", "Authorization code not found or already used.")
        del self.auth_codes[authorization_code.code]
        if client.client_id is None:
            raise TokenError("invalid_client", "Client ID is required")
        return self._issue_tokens(client.client_id, authorization_code.scopes, authorization_code.resource)

    async def load_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: str,
    ) -> RefreshToken | None:
        """Look up a refresh token previously issued to this client."""
        token = self.refresh_tokens.get(refresh_token)
        if token is None or token.client_id != client.client_id:
            return None
        return token

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        """Rotate a refresh token for a new access/refresh token pair."""
        if not set(scopes).issubset(set(refresh_token.scopes)):
            raise TokenError("invalid_scope", "Requested scopes exceed those authorized by the refresh token.")
        if client.client_id is None:
            raise TokenError("invalid_client", "Client ID is required")
        resource = self._refresh_resource.get(refresh_token.token)
        snapshot = self._token_state()
        try:
            self._revoke(
                access=self._refresh_to_access.get(refresh_token.token), refresh=refresh_token.token, save=False
            )
            return self._issue_tokens(client.client_id, scopes, resource)
        except OSError:
            # The rotation is one state change: put the old tokens back if the new state could not be saved.
            self._restore_token_state(snapshot)
            raise

    async def load_access_token(self, token: str) -> AccessToken | None:
        """Look up a still-valid access token, revoking it if it has expired."""
        access = self.access_tokens.get(token)
        if access is None:
            return None
        if access.expires_at is not None and access.expires_at < time.time():
            self._expire_access(token)
            self._save_state_best_effort()
            return None
        if not self._resource_matches(access.resource):
            return None
        return access

    async def verify_token(self, token: str) -> AccessToken | None:
        """Validate a bearer token for the TokenVerifier protocol."""
        return await self.load_access_token(token)

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        """Revoke an access or refresh token, and its linked counterpart."""
        if isinstance(token, AccessToken):
            self._revoke(access=token.token)
        else:
            self._revoke(refresh=token.token)

    def _issue_tokens(self, client_id: str, scopes: list[str], resource: str | None) -> OAuthToken:
        """Mint and store a fresh access/refresh token pair."""
        access_value = secrets.token_hex(32)
        refresh_value = secrets.token_hex(32)
        expires_at = int(time.time() + ACCESS_TOKEN_EXPIRY_SECONDS)
        self.access_tokens[access_value] = AccessToken(
            token=access_value,
            client_id=client_id,
            scopes=scopes,
            expires_at=expires_at,
            resource=resource,
        )
        # RefreshToken has no `resource` field - tracked separately so it can
        # be carried over to the next access token on rotation.
        self.refresh_tokens[refresh_value] = RefreshToken(
            token=refresh_value,
            client_id=client_id,
            scopes=scopes,
            expires_at=None,
        )
        self._refresh_resource[refresh_value] = resource
        self._access_to_refresh[access_value] = refresh_value
        self._refresh_to_access[refresh_value] = access_value
        self._save_state()
        return OAuthToken(
            access_token=access_value,
            token_type="Bearer",
            expires_in=ACCESS_TOKEN_EXPIRY_SECONDS,
            refresh_token=refresh_value,
            scope=" ".join(scopes),
        )

    def _expire_access(self, token: str) -> None:
        """Drop an expired access token, keeping its refresh token so the client can renew it."""
        self.access_tokens.pop(token, None)
        linked_refresh = self._access_to_refresh.pop(token, None)
        if linked_refresh:
            self._refresh_to_access.pop(linked_refresh, None)

    def _revoke(self, access: str | None = None, refresh: str | None = None, *, save: bool = True) -> None:
        """Revoke an access and/or refresh token, and its linked counterpart."""
        if access and access in self.access_tokens:
            del self.access_tokens[access]
            linked_refresh = self._access_to_refresh.pop(access, None)
            if linked_refresh:
                self.refresh_tokens.pop(linked_refresh, None)
                self._refresh_resource.pop(linked_refresh, None)
                self._refresh_to_access.pop(linked_refresh, None)
        if refresh and refresh in self.refresh_tokens:
            del self.refresh_tokens[refresh]
            self._refresh_resource.pop(refresh, None)
            linked_access = self._refresh_to_access.pop(refresh, None)
            if linked_access:
                self.access_tokens.pop(linked_access, None)
                self._access_to_refresh.pop(linked_access, None)
        if save:
            self._save_state()
