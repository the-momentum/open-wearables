"""Which auth provider the server attaches, depending on transport and configured secrets."""

import pytest
from pydantic import SecretStr

from app import main
from app.auth import SharedSecretVerifier
from app.config import settings


def _configure(monkeypatch: pytest.MonkeyPatch, *, transport: str, bearer: str = "") -> None:
    monkeypatch.setattr(settings, "mcp_transport", transport)
    monkeypatch.setattr(settings, "mcp_bearer_token", SecretStr(bearer))
    monkeypatch.setattr(settings, "mcp_oauth_password", SecretStr(""))


def test_no_auth_over_stdio_without_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch, transport="stdio")

    assert main._auth_provider_or_none() is None


def test_auth_is_attached_when_a_secret_is_set_even_over_stdio(monkeypatch: pytest.MonkeyPatch) -> None:
    # `fastmcp run app/main.py:mcp --transport http` leaves MCP_TRANSPORT at its stdio default.
    _configure(monkeypatch, transport="stdio", bearer="s3cret")

    assert isinstance(main._auth_provider_or_none(), SharedSecretVerifier)


def test_http_without_a_secret_refuses_to_start(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch, transport="http")

    with pytest.raises(SystemExit):
        main._auth_provider_or_none()
