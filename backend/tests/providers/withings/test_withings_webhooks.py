"""Withings notification screening and per-user notify subscription reconciliation."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, create_autospec, patch
from uuid import uuid4

import pytest
from fastapi import Request
from pydantic import SecretStr
from pytest_mock import MockerFixture
from sqlalchemy.orm import Session

from app.repositories.provider_settings_repository import ProviderSettingsRepository
from app.repositories.user_connection_repository import UserConnectionRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LiveSyncMode
from app.services.providers.withings import webhook_service
from app.services.providers.withings.data_247 import Withings247Data
from app.services.providers.withings.handlers.applis import SUBSCRIBED_APPLIS
from app.services.providers.withings.oauth import WithingsOAuth
from app.services.providers.withings.webhook_handler import WithingsWebhookHandler
from app.services.providers.withings.webhook_service import WithingsWebhookService
from app.services.providers.withings.workouts import WithingsWorkouts
from app.utils.exceptions import WebhookVerificationError

CALLBACK_URL = "https://example.com/api/v1/providers/withings/webhooks?token=secret"


def _handler(mode: LiveSyncMode = LiveSyncMode.WEBHOOK) -> WithingsWebhookHandler:
    handler = WithingsWebhookHandler(
        data_247=create_autospec(Withings247Data, instance=True),
        workouts=create_autospec(WithingsWorkouts, instance=True),
        default_live_sync_mode=mode,
    )
    handler.provider_settings_repo = create_autospec(ProviderSettingsRepository, instance=True)
    handler.provider_settings_repo.get_live_sync_mode.return_value = None
    return handler


def _request(token: str | None = "secret") -> MagicMock:
    request = create_autospec(Request, instance=True)
    request.query_params = {"token": token} if token is not None else {}
    return request


@pytest.fixture(autouse=True)
def _callback_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the real ``withings_callback_url()`` resolve to ``CALLBACK_URL``."""
    monkeypatch.setattr("app.config.settings.withings_webhook_token", SecretStr("secret"))
    monkeypatch.setattr("app.config.settings.api_base_url", "https://example.com")


# ---------------------------- inbound guards ----------------------------


def test_signature_requires_the_callback_token_and_a_userid() -> None:
    handler = _handler()
    assert handler.verify_signature(_request(), b"userid=42&appli=1") is True
    assert handler.verify_signature(_request("wrong"), b"userid=42&appli=1") is False
    assert handler.verify_signature(_request(), b"appli=1") is False


def test_probe_rejects_an_unauthenticated_head_request() -> None:
    assert _handler().handle_probe(_request()) is None
    with pytest.raises(WebhookVerificationError):
        _handler().handle_probe(_request(None))


@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        ({}, "invalid_payload_fields"),
        ({"userid": "42", "appli": 99}, "unhandled_appli: 99"),
        ({"userid": "42", "appli": 1}, "missing_date_range"),
        ({"userid": "42", "appli": 1, "startdate": 200, "enddate": 100}, "invalid_date_range"),
        ({"userid": "42", "appli": 1, "startdate": 0, "enddate": 60 * 60 * 24 * 40}, "date_range_too_large"),
        ({"userid": "42", "appli": 46, "action": "update"}, "profile_change"),
    ],
)
def test_dispatch_ignores_unusable_notifications(mocker: MockerFixture, payload: dict, reason: str) -> None:
    # Asserted through dispatch rather than the guards themselves: an ignored
    # notification must never reach the queue.
    mock_store = mocker.patch("app.services.providers.withings.webhook_handler.store_raw_payload", autospec=True)
    assert _handler().dispatch(MagicMock(spec=Session), payload)["reason"] == reason
    mock_store.assert_called_once()


def test_dispatch_ignores_data_notifications_while_in_pull_mode(mocker: MockerFixture) -> None:
    mocker.patch("app.services.providers.withings.webhook_handler.store_raw_payload", autospec=True)
    payload = {"userid": "42", "appli": 1, "startdate": 100, "enddate": 200}

    result = _handler(LiveSyncMode.PULL).dispatch(MagicMock(spec=Session), payload)

    assert result["reason"] == "live_sync_mode_not_webhook"


def test_dispatch_acknowledges_and_defers_the_fetch(mocker: MockerFixture) -> None:
    mock_send = mocker.patch("app.services.providers.withings.webhook_handler.celery_app.send_task", autospec=True)
    mock_store = mocker.patch("app.services.providers.withings.webhook_handler.store_raw_payload", autospec=True)
    handler = _handler()
    handler.connection_repo = create_autospec(UserConnectionRepository, instance=True)

    result = handler.dispatch(MagicMock(spec=Session), {"userid": "42", "appli": 1, "startdate": 100, "enddate": 200})

    assert result == {"status": "accepted", "appli": 1}
    mock_store.assert_called_once()
    assert mock_send.call_args.kwargs["queue"] == "webhook_sync"


def test_profile_delete_revokes_every_local_connection_for_that_account(mocker: MockerFixture) -> None:
    # One Withings account can back several local profiles; all lose access together.
    mock_revoked = mocker.patch("app.services.providers.withings.webhook_handler.on_connection_revoked", autospec=True)
    handler = _handler()
    handler.connection_repo = create_autospec(UserConnectionRepository, instance=True)
    connections = [
        SimpleNamespace(user_id=uuid4(), id=uuid4(), updated_at=datetime(2026, 3, 1, tzinfo=timezone.utc)),
        SimpleNamespace(user_id=uuid4(), id=uuid4(), updated_at=datetime(2026, 3, 1, tzinfo=timezone.utc)),
    ]
    handler.connection_repo.get_all_by_provider_user_id.return_value = connections
    handler.connection_repo.disconnect.return_value = True

    result = handler.process_payload(
        MagicMock(spec=Session), {"userid": "42", "appli": 46, "action": "delete"}, "trace"
    )

    assert result["status"] == "revoked"
    assert handler.connection_repo.disconnect.call_count == 2
    assert mock_revoked.call_count == 2


# ---------------------------- notify reconciliation ----------------------------


def _service() -> WithingsWebhookService:
    service = WithingsWebhookService(
        connection_repo=create_autospec(UserConnectionRepository, instance=True),
        oauth=create_autospec(WithingsOAuth, instance=True),
        default_live_sync_mode=LiveSyncMode.PULL,
    )
    service.provider_settings_repo = create_autospec(ProviderSettingsRepository, instance=True)
    return service


def test_reconcile_user_subscribes_every_missing_appli() -> None:
    service = _service()
    with (
        patch.object(service, "_list_subscriptions", autospec=True, return_value=[]),
        patch.object(
            service, "_change_subscription", autospec=True, return_value={"status": "subscribed"}
        ) as mock_change,
    ):
        results = service.sync_user(MagicMock(spec=Session), uuid4(), LiveSyncMode.WEBHOOK)

    assert len(results) == len(SUBSCRIBED_APPLIS)
    assert {call.args[2] for call in mock_change.call_args_list} == {"subscribe"}


def test_reconcile_user_revokes_our_own_profiles_when_switched_to_pull() -> None:
    service = _service()
    existing = [SimpleNamespace(appli=1, callbackurl=CALLBACK_URL, comment="open-wearables")]
    with (
        patch.object(service, "_list_subscriptions", autospec=True, return_value=existing),
        patch.object(service, "_change_subscription", autospec=True, return_value={"status": "revoked"}) as mock_change,
    ):
        service.sync_user(MagicMock(spec=Session), uuid4(), LiveSyncMode.PULL)

    assert mock_change.call_args.args[2] == "revoke"


def test_reconcile_user_leaves_profiles_registered_by_another_host_alone() -> None:
    service = _service()
    existing = [SimpleNamespace(appli=1, callbackurl="https://other.example/webhooks?token=x", comment=None)]
    with (
        patch.object(service, "_list_subscriptions", autospec=True, return_value=existing),
        patch.object(service, "_change_subscription", autospec=True) as mock_change,
    ):
        service.sync_user(MagicMock(spec=Session), uuid4(), LiveSyncMode.PULL)

    mock_change.assert_not_called()


def test_reconcile_user_skips_when_the_webhook_token_is_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.config.settings.withings_webhook_token", None)

    results = _service().sync_user(MagicMock(spec=Session), uuid4(), LiveSyncMode.WEBHOOK)

    assert results == [{"status": "skipped", "reason": "webhook_token_unconfigured"}]


def test_deregister_user_revokes_only_when_it_is_the_last_link(mocker: MockerFixture) -> None:
    # Subscriptions belong to the Withings account, so a sibling profile keeps them.
    mocker.patch("app.services.providers.withings.oauth.SessionLocal", autospec=True)
    mock_sync = mocker.patch(
        "app.services.providers.withings.webhook_service.WithingsWebhookService.sync_user", autospec=True
    )
    oauth = WithingsOAuth(
        user_repo=create_autospec(UserRepository, instance=True),
        connection_repo=create_autospec(UserConnectionRepository, instance=True),
        provider_name="withings",
        api_base_url="https://x",
    )
    user_id = uuid4()
    lookup = oauth.connection_repo.get_all_by_provider_user_id

    lookup.return_value = [SimpleNamespace(user_id=user_id), SimpleNamespace(user_id=uuid4())]
    oauth.deregister_user("at", provider_user_id="42")
    mock_sync.assert_not_called()

    lookup.return_value = [SimpleNamespace(user_id=user_id)]
    oauth.deregister_user("at", provider_user_id="42")

    # args[0] is the service instance the autospecced method was called on.
    assert mock_sync.call_args.args[2] == user_id
    assert mock_sync.call_args.args[3] == LiveSyncMode.PULL


def test_deregister_user_without_a_provider_user_id_does_nothing() -> None:
    oauth = WithingsOAuth(
        user_repo=create_autospec(UserRepository, instance=True),
        connection_repo=create_autospec(UserConnectionRepository, instance=True),
        provider_name="withings",
        api_base_url="https://x",
    )

    oauth.deregister_user("at", provider_user_id=None)

    oauth.connection_repo.get_all_by_provider_user_id.assert_not_called()


def test_callback_identity_is_exact_but_ownership_ignores_a_rotated_token() -> None:
    base = "https://example.com/api/v1/providers/withings/webhooks"
    assert webhook_service._urls_match(f"{base}?token=a", f"{base}/?token=a")
    assert not webhook_service._urls_match(f"{base}?token=a", f"{base}?token=b")
    # A rotated token still identifies the profile as ours; another host's does not.
    assert webhook_service._endpoints_match(f"{base}?token=old", f"{base}?token=new")
    assert not webhook_service._endpoints_match("https://other.example/webhooks?token=a", f"{base}?token=a")


def test_a_logged_callback_url_never_carries_the_token() -> None:
    assert "secret" not in webhook_service._redact("https://example.com/webhooks?token=secret")
