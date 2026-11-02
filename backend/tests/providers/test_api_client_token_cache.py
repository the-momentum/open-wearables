"""get_valid_token caches the token on the session, so a sync reads user_connection once."""

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException
from freezegun import freeze_time
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.integrations.redis_client import get_redis_client
from app.repositories import UserConnectionRepository
from app.services.providers import api_client
from app.services.providers.api_client import download_binary_content, get_valid_token, make_authenticated_request
from app.utils.exceptions import ReauthRequiredError
from tests.factories import UserConnectionFactory

API_BASE_URL = "https://api.example.com"


@pytest.fixture
def connection() -> Any:
    return UserConnectionFactory(provider="whoop", token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1))


@pytest.fixture
def repo() -> Any:
    repo = UserConnectionRepository()
    with patch.object(repo, "get_by_user_and_provider", wraps=repo.get_by_user_and_provider):
        yield repo


def _client_returning(*responses: httpx.Response) -> MagicMock:
    """Mock httpx.Client; sent Authorization headers land in ``client.sent_auth`` (copied, as the dict is reused)."""
    client = MagicMock()
    client.__enter__.return_value = client
    client.sent_auth = []
    pending = list(responses)

    def send(**kwargs: Any) -> httpx.Response:
        client.sent_auth.append(kwargs["headers"]["Authorization"])
        return pending.pop(0)

    client.request.side_effect = send
    return client


def _response(status_code: int, json: Any = None) -> httpx.Response:
    return httpx.Response(status_code, json=json, request=httpx.Request("GET", f"{API_BASE_URL}/v1/data"))


def _request(db: Session, connection: Any, repo: Any, oauth: Any = None) -> Any:
    return make_authenticated_request(
        db=db,
        user_id=connection.user_id,
        connection_repo=repo,
        oauth=oauth or MagicMock(),
        api_base_url=API_BASE_URL,
        provider_name="whoop",
        endpoint="/v1/data",
    )


def test_repeated_calls_read_connection_once(db: Session, connection: Any, repo: Any) -> None:
    tokens = [get_valid_token(db, connection.user_id, "whoop", repo, MagicMock()) for _ in range(5)]

    assert tokens == [connection.access_token] * 5
    assert repo.get_by_user_and_provider.call_count == 1


def test_cached_token_close_to_expiry_is_refreshed(db: Session, connection: Any, repo: Any) -> None:
    oauth = MagicMock()
    oauth.refresh_access_token.return_value.access_token = "refreshed"
    get_valid_token(db, connection.user_id, "whoop", repo, oauth)

    with freeze_time(datetime.now(timezone.utc) + timedelta(minutes=58)):
        token = get_valid_token(db, connection.user_id, "whoop", repo, oauth)

    assert token == "refreshed"
    oauth.refresh_access_token.assert_called_once()


def test_a_refreshed_token_is_reused(db: Session, connection: Any, repo: Any) -> None:
    def refresh(db_session: Session, _user_id: Any, refresh_token: str, **_: Any) -> Any:
        repo.update_tokens(db_session, connection, "refreshed", refresh_token, 3600)
        return MagicMock(access_token="refreshed")

    oauth = MagicMock()
    oauth.refresh_access_token.side_effect = refresh

    with freeze_time(datetime.now(timezone.utc) + timedelta(minutes=58)):
        tokens = [get_valid_token(db, connection.user_id, "whoop", repo, oauth) for _ in range(3)]

    assert tokens == ["refreshed"] * 3
    oauth.refresh_access_token.assert_called_once()
    # Both reads belong to the refresh itself: one before the lock, one inside it
    assert repo.get_by_user_and_provider.call_count == 2


def test_a_disconnect_made_elsewhere_is_seen_once_the_cached_token_ages(
    db: Session, connection: Any, repo: Any
) -> None:
    """A sync must not outlive a disconnect, or it writes back the data a purge just deleted."""
    clock = MagicMock()
    clock.monotonic.return_value = 0.0
    with patch.object(api_client, "time", clock):
        get_valid_token(db, connection.user_id, "whoop", repo, MagicMock())
        db.execute(text("UPDATE user_connection SET access_token = NULL WHERE id = :id"), {"id": connection.id})
        clock.monotonic.return_value = api_client.TOKEN_CACHE_TTL_SECONDS + 1

        with pytest.raises(HTTPException):
            get_valid_token(db, connection.user_id, "whoop", repo, MagicMock())


def test_request_retries_with_token_refreshed_elsewhere(db: Session, connection: Any, repo: Any) -> None:
    stale_token = get_valid_token(db, connection.user_id, "whoop", repo, MagicMock())
    # Raw SQL, like another worker's session: the connection instance in this session stays stale.
    db.execute(
        text("UPDATE user_connection SET access_token = 'refreshed-by-another-worker' WHERE id = :id"),
        {"id": connection.id},
    )
    client = _client_returning(_response(401), _response(200, json={"ok": True}))

    with patch("app.services.providers.api_client.httpx.Client", return_value=client):
        result = _request(db, connection, repo)

    assert result == {"ok": True}
    assert client.sent_auth == [f"Bearer {stale_token}", "Bearer refreshed-by-another-worker"]


def test_download_retries_with_token_refreshed_elsewhere(db: Session, connection: Any, repo: Any) -> None:
    stale_token = get_valid_token(db, connection.user_id, "whoop", repo, MagicMock())
    db.execute(
        text("UPDATE user_connection SET access_token = 'refreshed-by-another-worker' WHERE id = :id"),
        {"id": connection.id},
    )
    request = httpx.Request("GET", f"{API_BASE_URL}/file")
    sent_auth: list[str] = []

    def get(url: str, headers: dict[str, str], **kwargs: Any) -> httpx.Response:
        sent_auth.append(headers["Authorization"])
        status_code = 401 if len(sent_auth) == 1 else 200
        return httpx.Response(status_code, content=b"file", request=request)

    with patch("app.services.providers.api_client.httpx.get", side_effect=get):
        content = download_binary_content(db, connection.user_id, repo, MagicMock(), "whoop", f"{API_BASE_URL}/file")

    assert content == b"file"
    assert sent_auth == [f"Bearer {stale_token}", "Bearer refreshed-by-another-worker"]


def test_an_unchanged_rejected_token_is_refreshed_once_and_retried(db: Session, connection: Any, repo: Any) -> None:
    """A grant revoked at the provider shows up only when its refresh token is rejected too."""
    oauth = MagicMock()
    oauth.refresh_access_token.return_value.access_token = "refreshed"
    client = _client_returning(_response(401), _response(200, json={"ok": True}))

    with patch("app.services.providers.api_client.httpx.Client", return_value=client):
        result = _request(db, connection, repo, oauth)

    assert result == {"ok": True}
    assert client.sent_auth == [f"Bearer {connection.access_token}", "Bearer refreshed"]


def test_a_401_recovery_keeps_unflushed_changes_to_the_connection(db: Session, connection: Any, repo: Any) -> None:
    oauth = MagicMock()
    oauth.refresh_access_token.return_value.access_token = "refreshed"
    connection.scope = "changed in this session"
    client = _client_returning(_response(401), _response(200, json={"ok": True}))

    with patch("app.services.providers.api_client.httpx.Client", return_value=client):
        _request(db, connection, repo, oauth)

    assert connection.scope == "changed in this session"


def test_a_rejected_refresh_ends_the_request_as_reauth_required(db: Session, connection: Any, repo: Any) -> None:
    oauth = MagicMock()
    oauth.refresh_access_token.side_effect = ReauthRequiredError("whoop", connection.user_id, "reconnection required")
    client = _client_returning(_response(401))

    with (
        patch("app.services.providers.api_client.httpx.Client", return_value=client),
        pytest.raises(ReauthRequiredError),
    ):
        _request(db, connection, repo, oauth)

    assert client.request.call_count == 1


def test_a_401_after_a_successful_refresh_is_not_a_dead_grant(db: Session, connection: Any, repo: Any) -> None:
    """The refresh proved the grant alive, so the endpoint itself refused; nothing is revoked."""
    oauth = MagicMock()
    oauth.refresh_access_token.return_value.access_token = "refreshed"
    client = _client_returning(_response(401), _response(401))

    with (
        patch("app.services.providers.api_client.httpx.Client", return_value=client),
        pytest.raises(HTTPException) as exc_info,
    ):
        _request(db, connection, repo, oauth)

    assert not isinstance(exc_info.value, ReauthRequiredError)
    oauth.refresh_access_token.assert_called_once()
    oauth.revoke_connection.assert_not_called()


def test_without_a_refresh_token_a_401_is_not_retried(db: Session, connection: Any, repo: Any) -> None:
    """Polar has no refresh tokens and answers 401 on endpoints the user didn't consent to."""
    db.execute(text("UPDATE user_connection SET refresh_token = NULL WHERE id = :id"), {"id": connection.id})
    oauth = MagicMock()
    client = _client_returning(_response(401), _response(200, json={"ok": True}))

    with (
        patch("app.services.providers.api_client.httpx.Client", return_value=client),
        pytest.raises(HTTPException) as exc_info,
    ):
        _request(db, connection, repo, oauth)

    assert exc_info.value.status_code == 401
    assert client.request.call_count == 1
    oauth.revoke_connection.assert_not_called()


def _failing_since(connection: Any, hours_ago: float) -> str:
    key = f"provider_auth_failing_since:whoop:{connection.user_id}"
    get_redis_client().set(key, (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).timestamp())
    return key


def test_a_grant_that_only_fails_for_a_day_is_revoked(db: Session, connection: Any, repo: Any) -> None:
    """A revoke at a provider without refresh tokens, or a lapsed Oura membership, looks just like this."""
    _failing_since(connection, hours_ago=25)
    oauth = MagicMock()
    client = _client_returning(_response(403))

    with (
        patch("app.services.providers.api_client.httpx.Client", return_value=client),
        pytest.raises(ReauthRequiredError),
    ):
        _request(db, connection, repo, oauth)

    oauth.revoke_connection.assert_called_once_with(db, connection.user_id, reason="auth_failing")


def test_a_recent_rejection_is_not_yet_a_dead_grant(db: Session, connection: Any, repo: Any) -> None:
    oauth = MagicMock()
    client = _client_returning(_response(403))

    with (
        patch("app.services.providers.api_client.httpx.Client", return_value=client),
        pytest.raises(HTTPException) as exc_info,
    ):
        _request(db, connection, repo, oauth)

    assert not isinstance(exc_info.value, ReauthRequiredError)
    oauth.revoke_connection.assert_not_called()


def test_a_success_ends_the_failing_streak(db: Session, connection: Any, repo: Any) -> None:
    """Polar refuses some endpoints of a healthy grant; the others succeed, so it never adds up to a day."""
    key = _failing_since(connection, hours_ago=25)
    client = _client_returning(_response(200, json={"ok": True}))

    with patch("app.services.providers.api_client.httpx.Client", return_value=client):
        _request(db, connection, repo)

    assert get_redis_client().get(key) is None
