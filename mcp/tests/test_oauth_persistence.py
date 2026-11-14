"""OAuth clients and tokens survive a provider restart when a state file is set."""

import stat
from pathlib import Path

import pytest
from mcp.shared.auth import OAuthClientInformationFull

from app.oauth import SinglePasswordOAuthProvider


def _provider(state_file: Path) -> SinglePasswordOAuthProvider:
    return SinglePasswordOAuthProvider(base_url="https://example.test", state_file=state_file)


async def test_clients_and_tokens_survive_restart(tmp_path: Path) -> None:
    state_file = tmp_path / "oauth_state.json"
    first = _provider(state_file)
    client = OAuthClientInformationFull(client_id="c1", redirect_uris=["https://claude.ai/cb"])
    await first.register_client(client)
    issued = first._issue_tokens("c1", [], "https://example.test/mcp")

    second = _provider(state_file)
    assert await second.get_client("c1") is not None
    access = await second.load_access_token(issued.access_token)
    assert access is not None
    assert access.resource == "https://example.test/mcp"
    refresh = await second.load_refresh_token(client, issued.refresh_token)
    assert refresh is not None
    assert stat.S_IMODE(state_file.stat().st_mode) == 0o600


async def test_revoked_token_stays_revoked_after_restart(tmp_path: Path) -> None:
    state_file = tmp_path / "oauth_state.json"
    first = _provider(state_file)
    issued = first._issue_tokens("c1", [], None)
    first._revoke(access=issued.access_token)

    assert await _provider(state_file).load_access_token(issued.access_token) is None


async def test_corrupt_state_file_starts_empty(tmp_path: Path) -> None:
    state_file = tmp_path / "oauth_state.json"
    state_file.write_text("not json")

    provider = _provider(state_file)
    assert provider.clients == {}
    assert provider.access_tokens == {}
    assert (tmp_path / "oauth_state.json.corrupt").read_text() == "not json"


async def test_state_with_unexpected_shape_is_kept_aside_not_overwritten(tmp_path: Path) -> None:
    state_file = tmp_path / "oauth_state.json"
    state_file.write_text('{"clients": null, "access_tokens": {}, "refresh_tokens": {}}')

    provider = _provider(state_file)
    await provider.register_client(OAuthClientInformationFull(client_id="c1", redirect_uris=["https://claude.ai/cb"]))

    assert (tmp_path / "oauth_state.json.corrupt").exists()
    assert "c1" in _provider(state_file).clients


async def test_failed_write_is_not_reported_as_a_successful_revocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = _provider(tmp_path / "oauth_state.json")
    issued = provider._issue_tokens("c1", [], None)
    access = await provider.load_access_token(issued.access_token)
    assert access is not None

    def broken_replace(*args: object, **kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("app.oauth.os.replace", broken_replace)

    with pytest.raises(OSError, match="disk full"):
        await provider.revoke_token(access)
    # Fail closed: the token stays unusable in memory even though the file still lists it.
    assert await provider.load_access_token(issued.access_token) is None


async def test_housekeeping_does_not_fail_when_the_write_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider(tmp_path / "oauth_state.json")
    issued = provider._issue_tokens("c1", [], None)
    provider.access_tokens[issued.access_token].expires_at = 1

    def broken_replace(*args: object, **kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("app.oauth.os.replace", broken_replace)

    assert await provider.load_access_token(issued.access_token) is None
    provider._gc()


async def test_refresh_rotation_that_cannot_be_saved_keeps_the_old_tokens(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = _provider(tmp_path / "oauth_state.json")
    client = OAuthClientInformationFull(client_id="c1", redirect_uris=["https://claude.ai/cb"])
    issued = provider._issue_tokens("c1", [], None)
    refresh = await provider.load_refresh_token(client, issued.refresh_token)
    assert refresh is not None

    def broken_replace(*args: object, **kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("app.oauth.os.replace", broken_replace)

    with pytest.raises(OSError, match="disk full"):
        await provider.exchange_refresh_token(client, refresh, [])

    assert await provider.load_refresh_token(client, issued.refresh_token) is not None
    assert await provider.load_access_token(issued.access_token) is not None
    assert len(provider.access_tokens) == 1
    assert len(provider.refresh_tokens) == 1
