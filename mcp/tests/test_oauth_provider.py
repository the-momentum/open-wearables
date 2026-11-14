"""Behaviour of the OAuth provider's token lifecycle, login and registration."""

import time
from pathlib import Path

import pytest
from mcp.server.auth.provider import AuthorizationCode, AuthorizationParams, AuthorizeError
from mcp.shared.auth import OAuthClientInformationFull
from pydantic import AnyUrl
from starlette.requests import Request

from app.config import settings
from app.oauth import UNUSED_CLIENT_EXPIRY_SECONDS, SinglePasswordOAuthProvider, _PendingAuthorization


def _provider(state_file: Path | None = None) -> SinglePasswordOAuthProvider:
    return SinglePasswordOAuthProvider(base_url="https://example.test", state_file=state_file)


def _client(client_id: str = "c1") -> OAuthClientInformationFull:
    return OAuthClientInformationFull(
        client_id=client_id, redirect_uris=["https://claude.ai/cb"], client_id_issued_at=int(time.time())
    )


async def test_refresh_token_outlives_expired_access_token(tmp_path: Path) -> None:
    state_file = tmp_path / "oauth_state.json"
    provider = _provider(state_file)
    client = _client()
    await provider.register_client(client)
    issued = provider._issue_tokens("c1", [], None)
    provider.access_tokens[issued.access_token].expires_at = 1  # long past

    assert await provider.load_access_token(issued.access_token) is None

    for p in (provider, _provider(state_file)):
        refresh = await p.load_refresh_token(client, issued.refresh_token)
        assert refresh is not None
    renewed = await provider.exchange_refresh_token(client, refresh, [])
    assert await provider.load_access_token(renewed.access_token) is not None


async def test_gc_keeps_refresh_token_of_expired_access_token() -> None:
    provider = _provider()
    issued = provider._issue_tokens("c1", [], None)
    provider.access_tokens[issued.access_token].expires_at = 1

    provider._gc()

    assert issued.access_token not in provider.access_tokens
    assert issued.refresh_token in provider.refresh_tokens


def _request(headers: dict[str, str], peer: str = "172.18.0.1") -> Request:
    scope = {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": (peer, 1234),
    }
    return Request(scope)


def test_client_ip_is_the_socket_peer_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "mcp_client_ip_header", "")

    assert SinglePasswordOAuthProvider._client_ip(_request({"X-Forwarded-For": "9.9.9.9"})) == "172.18.0.1"


def test_client_ip_uses_the_configured_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "mcp_client_ip_header", "X-Forwarded-For")

    assert SinglePasswordOAuthProvider._client_ip(_request({"X-Forwarded-For": "6.6.6.6, 1.2.3.4"})) == "1.2.3.4"
    assert SinglePasswordOAuthProvider._client_ip(_request({})) == "172.18.0.1"


async def test_unused_clients_expire_so_registration_cannot_be_filled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.oauth.MAX_REGISTERED_CLIENTS", 2)
    provider = _provider()
    stale = int(time.time()) - 2 * UNUSED_CLIENT_EXPIRY_SECONDS
    for client_id in ("squat-1", "squat-2"):
        client = _client(client_id)
        client.client_id_issued_at = stale
        await provider.register_client(client)

    await provider.register_client(_client("claude"))

    assert set(provider.clients) == {"claude"}


async def test_client_holding_a_token_is_kept() -> None:
    provider = _provider()
    client = _client("c1")
    client.client_id_issued_at = int(time.time()) - 2 * UNUSED_CLIENT_EXPIRY_SECONDS
    await provider.register_client(client)
    provider._issue_tokens("c1", [], None)

    provider._gc()

    assert "c1" in provider.clients


async def test_login_page_for_an_expired_transaction_is_refused() -> None:
    provider = _provider()
    provider._pending["t"] = _PendingAuthorization(client=_client(), params=_params(), expires_at=1)
    request = Request({"type": "http", "headers": [], "query_string": b"txn=t"})

    response = await provider._handle_login_get(request)

    assert response.status_code == 400


def _params(resource: str | None = None) -> AuthorizationParams:
    return AuthorizationParams(
        state="s",
        scopes=[],
        code_challenge="x",
        redirect_uri=AnyUrl("https://claude.ai/cb"),
        redirect_uri_provided_explicitly=True,
        resource=resource,
    )


async def test_authorize_rejects_a_resource_that_is_not_this_server() -> None:
    provider = _provider()
    await provider.register_client(_client())

    with pytest.raises(AuthorizeError) as error:
        await provider.authorize(_client(), _params("https://other.example/mcp"))

    assert error.value.error == "invalid_target"
    assert await provider.authorize(_client(), _params("https://example.test/mcp"))
    assert await provider.authorize(_client(), _params())


async def test_token_for_another_resource_is_not_accepted() -> None:
    provider = _provider()
    issued = provider._issue_tokens("c1", [], "https://other.example/mcp")

    assert await provider.load_access_token(issued.access_token) is None


async def test_pending_authorizations_are_capped_per_client_and_overall(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.oauth.MAX_PENDING_AUTHORIZATIONS_PER_CLIENT", 2)
    monkeypatch.setattr("app.oauth.MAX_PENDING_AUTHORIZATIONS", 3)
    provider = _provider()
    for client_id in ("a", "b", "c"):
        await provider.register_client(_client(client_id))
    for _ in range(2):
        await provider.authorize(_client("a"), _params())

    with pytest.raises(AuthorizeError):
        await provider.authorize(_client("a"), _params())

    await provider.authorize(_client("b"), _params())
    with pytest.raises(AuthorizeError):
        await provider.authorize(_client("c"), _params())


def test_login_form_posts_under_the_public_url_prefix() -> None:
    provider = SinglePasswordOAuthProvider(base_url="https://example.test/wearables")

    page = provider._render_login("txn1", _client(), "https://claude.ai/cb")

    assert 'action="https://example.test/wearables/login"' in page


async def test_an_unused_client_expires_even_when_it_starts_an_authorization() -> None:
    provider = _provider()
    client = _client("squatter")
    client.client_id_issued_at = int(time.time()) - 2 * UNUSED_CLIENT_EXPIRY_SECONDS
    await provider.register_client(client)

    with pytest.raises(AuthorizeError) as error:
        await provider.authorize(client, _params())

    assert error.value.error == "unauthorized_client"
    assert "squatter" not in provider.clients
    assert provider._pending == {}


def test_gc_sweeps_expired_authorization_codes() -> None:
    provider = _provider()
    provider.auth_codes["old"] = AuthorizationCode(
        code="old",
        client_id="c1",
        redirect_uri=AnyUrl("https://claude.ai/cb"),
        redirect_uri_provided_explicitly=True,
        scopes=[],
        expires_at=1,
        code_challenge="x",
    )

    provider._gc()

    assert provider.auth_codes == {}
