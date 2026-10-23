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

from app.repositories import UserConnectionRepository
from app.services.providers.api_client import download_binary_content, get_valid_token, make_authenticated_request
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


def _request(db: Session, connection: Any, repo: Any) -> Any:
    return make_authenticated_request(
        db=db,
        user_id=connection.user_id,
        connection_repo=repo,
        oauth=MagicMock(),
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


def test_request_does_not_retry_when_token_is_unchanged(db: Session, connection: Any, repo: Any) -> None:
    client = _client_returning(_response(401), _response(200, json={"ok": True}))

    with (
        patch("app.services.providers.api_client.httpx.Client", return_value=client),
        pytest.raises(HTTPException) as exc_info,
    ):
        _request(db, connection, repo)

    assert exc_info.value.status_code == 401
    assert client.request.call_count == 1
