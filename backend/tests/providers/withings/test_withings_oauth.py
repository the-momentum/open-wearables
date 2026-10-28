"""Withings token RPC envelope handling and provider identity."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import httpx
import pytest

from app.schemas.auth import LiveSyncMode
from app.schemas.model_crud.credentials import OAuthTokenResponse
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.services.providers.withings.oauth import WithingsOAuth
from app.utils.exceptions import (
    AppError,
    InvalidInputError,
    ProviderError,
    ProviderRateLimitError,
    ProviderReauthorizationRequiredError,
)


def _oauth() -> WithingsOAuth:
    return WithingsOAuth(
        user_repo=MagicMock(),
        connection_repo=MagicMock(),
        provider_name="withings",
        api_base_url="https://wbsapi.withings.net",
    )


def _envelope(status: int, body: dict | None = None) -> MagicMock:
    response = MagicMock()
    response.json.return_value = {"status": status, "body": body or {}}
    response.raise_for_status.return_value = None
    return response


@patch("app.services.providers.withings.oauth.httpx.post")
def test_exchange_token_unwraps_the_envelope_body(mock_post: MagicMock) -> None:
    mock_post.return_value = _envelope(
        0, {"access_token": "at", "token_type": "Bearer", "refresh_token": "rt", "expires_in": 10800, "userid": 4242}
    )

    token = _oauth()._exchange_token("code-123", None)

    assert token.access_token == "at"
    payload = mock_post.call_args.kwargs["data"]
    assert payload["action"] == "requesttoken"
    assert payload["grant_type"] == "authorization_code"


@pytest.mark.parametrize(
    ("withings_status", "error_class", "http_status", "invalid_grant"),
    [
        (100, ProviderReauthorizationRequiredError, 409, True),
        (601, ProviderRateLimitError, 503, False),
        (247, ProviderError, 502, False),
    ],
)
@patch("app.services.providers.withings.oauth.httpx.post")
def test_refresh_classifies_provider_statuses(
    mock_post: MagicMock,
    withings_status: int,
    error_class: type[AppError],
    http_status: int,
    invalid_grant: bool,
) -> None:
    mock_post.return_value = _envelope(withings_status)
    oauth = _oauth()

    with patch.object(oauth, "_revoke_connection") as mock_revoke, pytest.raises(AppError) as exc_info:
        oauth.refresh_access_token(MagicMock(), uuid4(), "old-rt")

    assert type(exc_info.value) is error_class
    assert exc_info.value.status_code == http_status
    # a refresh refused as bad input (247) is a request we built wrong, so it reaches Sentry
    assert getattr(exc_info.value, "request_rejected", False) is (withings_status == 247)
    # Only a spent grant is terminal; the others are worth retrying with the same token.
    assert mock_revoke.called is invalid_grant


@pytest.mark.parametrize(("http_status", "request_rejected"), [(403, True), (404, True), (503, False)])
@patch("app.services.providers.withings.oauth.httpx.post")
def test_refresh_http_error_is_reported_unless_an_outage(
    mock_post: MagicMock, http_status: int, request_rejected: bool
) -> None:
    request = httpx.Request("POST", "https://wbsapi.withings.net/v2/oauth2")
    mock_post.return_value = httpx.Response(http_status, text="error", request=request)
    oauth = _oauth()

    with patch.object(oauth, "_revoke_connection") as mock_revoke, pytest.raises(ProviderError) as exc_info:
        oauth.refresh_access_token(MagicMock(), uuid4(), "old-rt")

    assert type(exc_info.value) is ProviderError
    assert exc_info.value.upstream_status == http_status
    # The token endpoint has no per-user resource: a 4xx there means our integration broke.
    assert exc_info.value.request_rejected is request_rejected
    mock_revoke.assert_not_called()


@pytest.mark.parametrize("withings_status", [100, 247])
@patch("app.services.providers.withings.oauth.httpx.post")
def test_rejected_authorization_code_is_a_client_error(mock_post: MagicMock, withings_status: int) -> None:
    mock_post.return_value = _envelope(withings_status)

    with pytest.raises(InvalidInputError):
        _oauth()._exchange_token("expired-code", None)


@patch("app.services.providers.withings.oauth.httpx.post")
def test_refresh_keeps_the_old_refresh_token_when_withings_omits_one(mock_post: MagicMock) -> None:
    mock_post.return_value = _envelope(0, {"access_token": "new-at", "token_type": "Bearer", "expires_in": 10800})
    oauth = _oauth()
    connection = MagicMock()
    oauth.connection_repo.get_by_user_and_provider.return_value = connection

    oauth.refresh_access_token(MagicMock(), uuid4(), "old-rt")

    args = oauth.connection_repo.update_tokens.call_args.args
    assert args[2] == "new-at"
    assert args[3] == "old-rt"


def test_provider_user_info_reads_userid_from_the_token_body() -> None:
    body = {"access_token": "at", "token_type": "Bearer", "expires_in": 1, "userid": 4242}
    token = OAuthTokenResponse.model_validate(body)

    assert _oauth()._get_provider_user_info(token, "local-user")["user_id"] == "4242"


@pytest.mark.parametrize(
    ("stored_mode", "enqueued"),
    [(LiveSyncMode.WEBHOOK, True), (LiveSyncMode.PULL, False), (None, False)],
)
@patch("app.services.providers.withings.oauth.celery_app.send_task")
@patch("app.services.providers.withings.oauth.ProviderSettingsRepository")
@patch.object(BaseOAuthTemplate, "_save_connection")
def test_save_connection_enqueues_subscriptions_only_in_webhook_mode(
    mock_super: MagicMock,
    mock_repo: MagicMock,
    mock_send: MagicMock,
    stored_mode: LiveSyncMode | None,
    enqueued: bool,
) -> None:
    mock_repo.return_value.get_live_sync_mode.return_value = stored_mode
    user_id = uuid4()
    token = OAuthTokenResponse.model_validate({"access_token": "at", "token_type": "Bearer", "expires_in": 1})

    _oauth()._save_connection(MagicMock(), user_id, token, {}, MagicMock())

    # The connection is always persisted; only the subscribe step is conditional.
    mock_super.assert_called_once()
    assert mock_send.called is enqueued
    if enqueued:
        assert mock_send.call_args.kwargs["args"] == [str(user_id)]


@patch("app.services.providers.withings.oauth.celery_app.send_task", side_effect=RuntimeError("broker down"))
@patch("app.services.providers.withings.oauth.ProviderSettingsRepository")
@patch.object(BaseOAuthTemplate, "_save_connection")
def test_save_connection_survives_a_broker_failure(
    mock_super: MagicMock, mock_repo: MagicMock, mock_send: MagicMock
) -> None:
    # The account is linked by this point; scheduling must not fail the callback.
    mock_repo.return_value.get_live_sync_mode.return_value = LiveSyncMode.WEBHOOK
    token = OAuthTokenResponse.model_validate({"access_token": "at", "token_type": "Bearer", "expires_in": 1})

    _oauth()._save_connection(MagicMock(), uuid4(), token, {}, MagicMock())

    mock_send.assert_called_once()
    mock_super.assert_called_once()
