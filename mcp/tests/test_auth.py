"""Bearer-token auth for the HTTP transport."""

import pytest
from pydantic import SecretStr

from app.auth import SharedSecretVerifier, secrets_match
from app.config import settings


async def test_bearer_verifier_handles_non_ascii_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "mcp_bearer_token", SecretStr("sécret-tøken"))
    verifier = SharedSecretVerifier()

    assert await verifier.verify_token("sécret-tøken") is not None
    assert await verifier.verify_token("wrong-é") is None


def test_secrets_match_compares_non_ascii_as_utf8() -> None:
    assert secrets_match("pässword", "pässword")
    assert not secrets_match("pässword", "password")
