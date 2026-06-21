"""Tests for WithingsOAuth — envelope unwrapping, action param, userid extraction."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import User
from app.repositories.user_connection_repository import UserConnectionRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import AuthenticationMethod
from app.schemas.model_crud.credentials import OAuthTokenResponse
from app.services.providers.withings.applis import SUBSCRIBED_APPLIS
from app.services.providers.withings.oauth import WithingsOAuth
from tests.factories import UserConnectionFactory, UserFactory


@pytest.fixture
def withings_oauth() -> WithingsOAuth:
    return WithingsOAuth(
        user_repo=UserRepository(User),
        connection_repo=UserConnectionRepository(),
        provider_name="withings",
        api_base_url="https://wbsapi.withings.net",
    )


def test_endpoints(withings_oauth: WithingsOAuth) -> None:
    e = withings_oauth.endpoints
    assert e.authorize_url == "https://account.withings.com/oauth2_user/authorize2"
    assert e.token_url == "https://wbsapi.withings.net/v2/oauth2"


def test_auth_method_is_body_and_no_pkce(withings_oauth: WithingsOAuth) -> None:
    assert withings_oauth.auth_method == AuthenticationMethod.BODY
    assert withings_oauth.use_pkce is False


def test_authorization_url_is_standard(withings_oauth: WithingsOAuth) -> None:
    url, state = withings_oauth.get_authorization_url(uuid4())
    assert url.startswith("https://account.withings.com/oauth2_user/authorize2?")
    assert "response_type=code" in url
    assert f"state={state}" in url


@patch("httpx.post")
def test_exchange_token_unwraps_envelope(mock_post: MagicMock, withings_oauth: WithingsOAuth) -> None:
    mock_post.return_value = MagicMock(
        status_code=200,
        raise_for_status=MagicMock(return_value=None),
        json=MagicMock(
            return_value={
                "status": 0,
                "body": {
                    "userid": "999",
                    "access_token": "at",
                    "refresh_token": "rt",
                    "scope": "user.info",
                    "expires_in": 10800,
                    "token_type": "Bearer",
                },
            }
        ),
    )
    resp = withings_oauth._exchange_token("the_code", None)
    assert isinstance(resp, OAuthTokenResponse)
    assert resp.access_token == "at"
    assert resp.refresh_token == "rt"
    assert resp.expires_in == 10800
    # action=requesttoken + grant_type sent in the BODY
    sent = mock_post.call_args.kwargs["data"]
    assert sent["action"] == "requesttoken"
    assert sent["grant_type"] == "authorization_code"
    assert sent["code"] == "the_code"


@patch("httpx.post")
def test_exchange_token_raises_on_nonzero_status(mock_post: MagicMock, withings_oauth: WithingsOAuth) -> None:
    # Auth-error status (342 is in _AUTH_ERROR_STATUSES) → HTTP 400
    mock_post.return_value = MagicMock(
        status_code=200,
        raise_for_status=MagicMock(return_value=None),
        json=MagicMock(return_value={"status": 342, "body": {}}),
    )
    with pytest.raises(HTTPException) as exc_info:
        withings_oauth._exchange_token("bad", None)
    assert exc_info.value.status_code == 400

    # Non-auth-error status (123 is NOT in _AUTH_ERROR_STATUSES) → HTTP 500
    mock_post.return_value = MagicMock(
        status_code=200,
        raise_for_status=MagicMock(return_value=None),
        json=MagicMock(return_value={"status": 123, "body": {}}),
    )
    with pytest.raises(HTTPException) as exc_info:
        withings_oauth._exchange_token("bad", None)
    assert exc_info.value.status_code == 500


def test_user_info_reads_userid_from_token_body(withings_oauth: WithingsOAuth) -> None:
    token = OAuthTokenResponse(
        access_token="at",
        refresh_token="rt",
        expires_in=10800,
        token_type="Bearer",
        userid="12345",
    )
    info = withings_oauth._get_provider_user_info(token, "internal-user")
    assert info["user_id"] == "12345"


@patch("httpx.post")
def test_refresh_persists_rotated_token(mock_post: MagicMock, withings_oauth: WithingsOAuth, db: Session) -> None:
    user = UserFactory()
    conn = UserConnectionFactory(user=user, provider="withings", refresh_token="old_rt")
    mock_post.return_value = MagicMock(
        status_code=200,
        raise_for_status=MagicMock(return_value=None),
        json=MagicMock(
            return_value={
                "status": 0,
                "body": {
                    "userid": "999",
                    "access_token": "new_at",
                    "refresh_token": "new_rt",
                    "expires_in": 10800,
                    "token_type": "Bearer",
                },
            }
        ),
    )
    resp = withings_oauth.refresh_access_token(db, user.id, "old_rt")
    assert resp.access_token == "new_at"
    assert resp.refresh_token == "new_rt"
    sent = mock_post.call_args.kwargs["data"]
    assert sent["action"] == "requesttoken"
    assert sent["grant_type"] == "refresh_token"

    # Verify the rotated tokens were persisted to the DB
    db.refresh(conn)
    assert conn.refresh_token == "new_rt"
    assert conn.access_token == "new_at"


def test_user_info_returns_none_when_userid_absent(withings_oauth: WithingsOAuth) -> None:
    token = OAuthTokenResponse(
        access_token="at",
        refresh_token="rt",
        expires_in=10800,
        token_type="Bearer",
    )
    info = withings_oauth._get_provider_user_info(token, "internal")
    assert info["user_id"] is None


@patch("httpx.post")
def test_deregister_user_revokes_every_subscribed_appli(mock_post: MagicMock, withings_oauth: WithingsOAuth) -> None:
    mock_post.return_value = MagicMock(
        status_code=200,
        raise_for_status=MagicMock(return_value=None),
        json=MagicMock(return_value={"status": 0}),
    )
    withings_oauth.deregister_user("the_token")

    assert mock_post.call_count == len(SUBSCRIBED_APPLIS)
    sent_appli = set()
    for call in mock_post.call_args_list:
        assert call.args[0].endswith("/notify")
        assert call.kwargs["data"]["action"] == "revoke"
        assert call.kwargs["headers"]["Authorization"] == "Bearer the_token"
        sent_appli.add(call.kwargs["data"]["appli"])
    assert sent_appli == set(SUBSCRIBED_APPLIS)


@patch("app.services.providers.withings.oauth.log_structured")
@patch("httpx.post")
def test_deregister_user_logs_nonzero_envelope_status(
    mock_post: MagicMock,
    mock_log: MagicMock,
    withings_oauth: WithingsOAuth,
) -> None:
    mock_post.return_value = MagicMock(
        status_code=200,
        raise_for_status=MagicMock(return_value=None),
        json=MagicMock(return_value={"status": 293}),
    )
    withings_oauth.deregister_user("the_token")
    assert mock_log.call_count == len(SUBSCRIBED_APPLIS)
    assert all(call.kwargs["withings_status"] == 293 for call in mock_log.call_args_list)


@patch("httpx.post")
def test_deregister_user_is_best_effort_and_never_raises(mock_post: MagicMock, withings_oauth: WithingsOAuth) -> None:
    mock_post.side_effect = httpx.HTTPError("boom")
    withings_oauth.deregister_user("the_token")  # must not raise
    assert mock_post.call_count == len(SUBSCRIBED_APPLIS)
