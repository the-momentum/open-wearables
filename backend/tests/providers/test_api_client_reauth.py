"""Dead grants raise ReauthRequiredError, and revoke the connection unless the caller does it itself."""

import time
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest
from sqlalchemy.orm import Session

from app.integrations.redis_client import get_redis_client
from app.repositories import UserConnectionRepository
from app.services.providers.api_client import (
    DEAD_GRANT_AFTER,
    _failing_since_key,
    get_valid_token,
    make_authenticated_request,
)
from app.utils.exceptions import ReauthRequiredError
from tests.factories import UserConnectionFactory


@pytest.fixture
def dead_connection() -> Any:
    return UserConnectionFactory(
        provider="whoop",
        refresh_token=None,
        token_expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )


@pytest.mark.parametrize("revoke_on_failure", [True, False])
def test_no_refresh_token_raises_reauth_required(db: Session, dead_connection: Any, revoke_on_failure: bool) -> None:
    oauth = MagicMock()
    with pytest.raises(ReauthRequiredError) as exc_info:
        get_valid_token(
            db,
            dead_connection.user_id,
            "whoop",
            UserConnectionRepository(),
            oauth,
            revoke_on_failure=revoke_on_failure,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.user_id == dead_connection.user_id
    if revoke_on_failure:
        oauth.revoke_connection.assert_called_once_with(db, dead_connection.user_id, reason="no_refresh_token")
    else:
        oauth.revoke_connection.assert_not_called()


def test_no_refresh_token_within_buffer_returns_still_valid_token(db: Session) -> None:
    connection = UserConnectionFactory(
        provider="whoop",
        refresh_token=None,
        token_expires_at=datetime.now(timezone.utc) + timedelta(minutes=2),
    )
    oauth = MagicMock()

    token = get_valid_token(db, connection.user_id, "whoop", UserConnectionRepository(), oauth)

    assert token == connection.access_token
    oauth.revoke_connection.assert_not_called()
    oauth.refresh_access_token.assert_not_called()


def _request(db: Session, connection: Any, oauth: MagicMock, status_code: int, *, revoke_on_failure: bool) -> None:
    response = httpx.Response(status_code, json={}, request=httpx.Request("GET", "https://api.example.com/x"))
    client = MagicMock()
    client.__enter__.return_value.request.return_value = response
    with patch("app.services.providers.api_client.httpx.Client", return_value=client):
        make_authenticated_request(
            db,
            connection.user_id,
            UserConnectionRepository(),
            oauth,
            "https://api.example.com",
            "whoop",
            "/x",
            revoke_on_failure=revoke_on_failure,
        )


@pytest.mark.parametrize("revoke_on_failure", [True, False])
def test_rejected_token_refreshes_with_callers_revoke_choice(db: Session, revoke_on_failure: bool) -> None:
    connection: Any = UserConnectionFactory(provider="whoop")
    oauth = MagicMock()
    oauth.refresh_access_token.side_effect = ReauthRequiredError("whoop", connection.user_id, "reconnection required")

    with pytest.raises(ReauthRequiredError):
        _request(db, connection, oauth, 401, revoke_on_failure=revoke_on_failure)

    oauth.refresh_access_token.assert_called_once_with(
        db, connection.user_id, connection.refresh_token, revoke_on_failure=revoke_on_failure
    )


@pytest.mark.parametrize("revoke_on_failure", [True, False])
def test_grant_failing_for_a_day_raises_reauth_required(db: Session, revoke_on_failure: bool) -> None:
    connection: Any = UserConnectionFactory(provider="whoop")
    failing_since = time.time() - DEAD_GRANT_AFTER.total_seconds() - 60
    get_redis_client().set(_failing_since_key("whoop", connection.user_id), failing_since)
    oauth = MagicMock()

    with pytest.raises(ReauthRequiredError):
        _request(db, connection, oauth, 403, revoke_on_failure=revoke_on_failure)

    if revoke_on_failure:
        oauth.revoke_connection.assert_called_once_with(db, connection.user_id, reason="auth_failing")
    else:
        oauth.revoke_connection.assert_not_called()
