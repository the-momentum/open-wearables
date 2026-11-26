"""Dead grants raise ReauthRequiredError, and revoke the connection unless the caller does it itself."""

import time
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock, create_autospec

import pytest
import respx
from sqlalchemy.orm import Session

from app.integrations.redis_client import get_redis_client
from app.repositories import UserConnectionRepository
from app.services.providers.api_client import (
    DEAD_GRANT_AFTER,
    _failing_since_key,
    get_valid_token,
    make_authenticated_request,
)
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.utils.exceptions import ReauthRequiredError
from tests.factories import UserConnectionFactory

API_BASE_URL = "https://api.example.com"


@pytest.fixture
def dead_connection() -> Any:
    return UserConnectionFactory(
        provider="whoop",
        refresh_token=None,
        token_expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )


@pytest.mark.parametrize("revoke_on_failure", [True, False])
def test_no_refresh_token_raises_reauth_required(db: Session, dead_connection: Any, revoke_on_failure: bool) -> None:
    oauth = create_autospec(BaseOAuthTemplate, instance=True)
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
    oauth = create_autospec(BaseOAuthTemplate, instance=True)

    token = get_valid_token(db, connection.user_id, "whoop", UserConnectionRepository(), oauth)

    assert token == connection.access_token
    oauth.revoke_connection.assert_not_called()
    oauth.refresh_access_token.assert_not_called()


def _request(
    respx_mock: respx.MockRouter,
    db: Session,
    connection: Any,
    oauth: MagicMock,
    status_code: int,
    *,
    revoke_on_failure: bool,
) -> None:
    respx_mock.get(f"{API_BASE_URL}/x").respond(status_code, json={})
    make_authenticated_request(
        db,
        connection.user_id,
        UserConnectionRepository(),
        oauth,
        API_BASE_URL,
        "whoop",
        "/x",
        revoke_on_failure=revoke_on_failure,
    )


@pytest.mark.parametrize("revoke_on_failure", [True, False])
def test_rejected_token_refreshes_with_callers_revoke_choice(
    respx_mock: respx.MockRouter, db: Session, revoke_on_failure: bool
) -> None:
    connection: Any = UserConnectionFactory(provider="whoop")
    oauth = create_autospec(BaseOAuthTemplate, instance=True)
    oauth.refresh_access_token.side_effect = ReauthRequiredError("whoop", connection.user_id, "reconnection required")

    with pytest.raises(ReauthRequiredError):
        _request(respx_mock, db, connection, oauth, 401, revoke_on_failure=revoke_on_failure)

    oauth.refresh_access_token.assert_called_once_with(
        db, connection.user_id, connection.refresh_token, revoke_on_failure=revoke_on_failure
    )


@pytest.mark.parametrize("revoke_on_failure", [True, False])
def test_grant_failing_for_a_day_raises_reauth_required(
    respx_mock: respx.MockRouter, db: Session, revoke_on_failure: bool
) -> None:
    connection: Any = UserConnectionFactory(provider="whoop")
    failing_since = time.time() - DEAD_GRANT_AFTER.total_seconds() - 60
    get_redis_client().set(_failing_since_key("whoop", connection.user_id), failing_since)
    oauth = create_autospec(BaseOAuthTemplate, instance=True)

    with pytest.raises(ReauthRequiredError):
        _request(respx_mock, db, connection, oauth, 403, revoke_on_failure=revoke_on_failure)

    if revoke_on_failure:
        oauth.revoke_connection.assert_called_once_with(db, connection.user_id, reason="auth_failing")
    else:
        oauth.revoke_connection.assert_not_called()
