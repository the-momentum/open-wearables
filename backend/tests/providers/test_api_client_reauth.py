"""get_valid_token treats an expired token with no refresh token as a dead grant."""

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.repositories import UserConnectionRepository
from app.services.providers.api_client import get_valid_token
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

    assert exc_info.value.status_code == 401
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
