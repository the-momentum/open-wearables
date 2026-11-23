"""Withings token RPC envelope handling and provider identity."""

from unittest.mock import MagicMock, create_autospec, patch
from uuid import uuid4

import httpx
import pytest
import respx
from pytest_mock import MockerFixture
from sqlalchemy.orm import Session

from app.models import UserConnection
from app.repositories.user_connection_repository import UserConnectionRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LiveSyncMode
from app.schemas.model_crud.credentials import OAuthState, OAuthTokenResponse
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.services.providers.withings.oauth import WithingsOAuth
from app.utils.exceptions import (
    AppError,
    InvalidInputError,
    ProviderError,
    ProviderRateLimitError,
    ReauthRequiredError,
)

TOKEN_URL = "https://wbsapi.withings.net/v2/oauth2"


def _oauth() -> WithingsOAuth:
    return WithingsOAuth(
        user_repo=create_autospec(UserRepository, instance=True),
        connection_repo=create_autospec(UserConnectionRepository, instance=True),
        provider_name="withings",
        api_base_url="https://wbsapi.withings.net",
    )


def _envelope(status: int, body: dict | None = None) -> dict:
    """Withings answers HTTP 200 and reports the outcome in the ``status`` of this envelope."""
    return {"status": status, "body": body or {}}


def test_exchange_token_unwraps_the_envelope_body(respx_mock: respx.MockRouter) -> None:
    route = respx_mock.post(TOKEN_URL).respond(
        200,
        json=_envelope(
            0,
            {"access_token": "at", "token_type": "Bearer", "refresh_token": "rt", "expires_in": 10800, "userid": 4242},
        ),
    )

    token = _oauth()._exchange_token("code-123", None)

    assert token.access_token == "at"
    payload = httpx.QueryParams(route.calls.last.request.content.decode())
    assert payload["action"] == "requesttoken"
    assert payload["grant_type"] == "authorization_code"


@pytest.mark.parametrize(
    ("withings_status", "error_class", "http_status", "invalid_grant"),
    [
        (100, ReauthRequiredError, 409, True),
        (601, ProviderRateLimitError, 503, False),
        (247, ProviderError, 502, False),
    ],
)
def test_refresh_classifies_provider_statuses(
    respx_mock: respx.MockRouter,
    withings_status: int,
    error_class: type[AppError],
    http_status: int,
    invalid_grant: bool,
) -> None:
    respx_mock.post(TOKEN_URL).respond(200, json=_envelope(withings_status))
    oauth = _oauth()

    with patch.object(oauth, "revoke_connection", autospec=True) as mock_revoke, pytest.raises(AppError) as exc_info:
        oauth.refresh_access_token(MagicMock(spec=Session), uuid4(), "old-rt")

    assert type(exc_info.value) is error_class
    assert exc_info.value.status_code == http_status
    # a refresh refused as bad input (247) is a request we built wrong, so it reaches Sentry
    assert getattr(exc_info.value, "request_rejected", False) is (withings_status == 247)
    # Only a spent grant is terminal; the others are worth retrying with the same token.
    assert mock_revoke.called is invalid_grant


@pytest.mark.parametrize(("http_status", "request_rejected"), [(403, True), (404, True), (503, False)])
def test_refresh_http_4xx_is_a_refused_request(
    respx_mock: respx.MockRouter, http_status: int, request_rejected: bool
) -> None:
    respx_mock.post(TOKEN_URL).respond(http_status, text="error")
    oauth = _oauth()

    with (
        patch.object(oauth, "revoke_connection", autospec=True) as mock_revoke,
        pytest.raises(ProviderError) as exc_info,
    ):
        oauth.refresh_access_token(MagicMock(spec=Session), uuid4(), "old-rt")

    assert type(exc_info.value) is ProviderError
    assert exc_info.value.upstream_status == http_status
    # The token endpoint has no per-user resource: a 4xx there means our integration broke.
    assert exc_info.value.request_rejected is request_rejected
    mock_revoke.assert_not_called()


@pytest.mark.parametrize("withings_status", [100, 247])
def test_rejected_authorization_code_is_a_client_error(respx_mock: respx.MockRouter, withings_status: int) -> None:
    respx_mock.post(TOKEN_URL).respond(200, json=_envelope(withings_status))

    with pytest.raises(InvalidInputError):
        _oauth()._exchange_token("expired-code", None)


def test_refresh_keeps_the_old_refresh_token_when_withings_omits_one(respx_mock: respx.MockRouter) -> None:
    respx_mock.post(TOKEN_URL).respond(
        200, json=_envelope(0, {"access_token": "new-at", "token_type": "Bearer", "expires_in": 10800})
    )
    oauth = _oauth()
    connection = UserConnection()
    oauth.connection_repo.get_by_user_and_provider.return_value = connection

    oauth.refresh_access_token(MagicMock(spec=Session), uuid4(), "old-rt")

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
def test_save_connection_enqueues_subscriptions_only_in_webhook_mode(
    mocker: MockerFixture, stored_mode: LiveSyncMode | None, enqueued: bool
) -> None:
    mock_super = mocker.patch.object(BaseOAuthTemplate, "_save_connection", autospec=True)
    mock_repo = mocker.patch("app.services.providers.withings.oauth.ProviderSettingsRepository", autospec=True)
    mock_send = mocker.patch("app.services.providers.withings.oauth.celery_app.send_task", autospec=True)
    mock_repo.return_value.get_live_sync_mode.return_value = stored_mode
    user_id = uuid4()
    token = OAuthTokenResponse.model_validate({"access_token": "at", "token_type": "Bearer", "expires_in": 1})

    _oauth()._save_connection(
        MagicMock(spec=Session), user_id, token, {}, OAuthState(user_id=user_id, provider="withings")
    )

    # The connection is always persisted; only the subscribe step is conditional.
    mock_super.assert_called_once()
    assert mock_send.called is enqueued
    if enqueued:
        assert mock_send.call_args.kwargs["args"] == [str(user_id)]


def test_save_connection_survives_a_broker_failure(mocker: MockerFixture) -> None:
    # The account is linked by this point; scheduling must not fail the callback.
    mock_super = mocker.patch.object(BaseOAuthTemplate, "_save_connection", autospec=True)
    mock_repo = mocker.patch("app.services.providers.withings.oauth.ProviderSettingsRepository", autospec=True)
    mock_send = mocker.patch(
        "app.services.providers.withings.oauth.celery_app.send_task",
        autospec=True,
        side_effect=RuntimeError("broker down"),
    )
    mock_repo.return_value.get_live_sync_mode.return_value = LiveSyncMode.WEBHOOK
    token = OAuthTokenResponse.model_validate({"access_token": "at", "token_type": "Bearer", "expires_in": 1})

    _oauth()._save_connection(
        MagicMock(spec=Session), uuid4(), token, {}, OAuthState(user_id=uuid4(), provider="withings")
    )

    mock_send.assert_called_once()
    mock_super.assert_called_once()
