"""Withings notification screening and per-user notify subscription reconciliation."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from pydantic import SecretStr

from app.schemas.auth import LiveSyncMode
from app.services.providers.withings import webhook_service
from app.services.providers.withings.applis import SUBSCRIBED_APPLIS
from app.services.providers.withings.oauth import WithingsOAuth
from app.services.providers.withings.webhook_handler import WithingsWebhookHandler
from app.services.providers.withings.webhook_service import WithingsWebhookService

CALLBACK_URL = "https://example.com/api/v1/providers/withings/webhooks?token=secret"


def _handler(mode: LiveSyncMode = LiveSyncMode.WEBHOOK) -> WithingsWebhookHandler:
    handler = WithingsWebhookHandler(data_247=MagicMock(), workouts=MagicMock(), default_live_sync_mode=mode)
    handler.provider_settings_repo = MagicMock()
    handler.provider_settings_repo.get_live_sync_mode.return_value = None
    return handler


def _request(token: str | None = "secret") -> MagicMock:
    request = MagicMock()
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
    from fastapi import HTTPException

    assert _handler().handle_probe(_request()) is None
    with pytest.raises(HTTPException):
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
@patch("app.services.providers.withings.webhook_handler.store_raw_payload")
def test_dispatch_ignores_unusable_notifications(mock_store: MagicMock, payload: dict, reason: str) -> None:
    # Asserted through dispatch rather than the guards themselves: an ignored
    # notification must never reach the queue.
    assert _handler().dispatch(MagicMock(), payload)["reason"] == reason
    mock_store.assert_called_once()


@patch("app.services.providers.withings.webhook_handler.store_raw_payload")
def test_dispatch_ignores_data_notifications_while_in_pull_mode(mock_store: MagicMock) -> None:
    payload = {"userid": "42", "appli": 1, "startdate": 100, "enddate": 200}

    result = _handler(LiveSyncMode.PULL).dispatch(MagicMock(), payload)

    assert result["reason"] == "live_sync_mode_not_webhook"


@patch("app.services.providers.withings.webhook_handler.store_raw_payload")
@patch("app.services.providers.withings.webhook_handler.celery_app.send_task")
def test_dispatch_acknowledges_and_defers_the_fetch(mock_send: MagicMock, mock_store: MagicMock) -> None:
    handler = _handler()
    handler.connection_repo = MagicMock()

    result = handler.dispatch(MagicMock(), {"userid": "42", "appli": 1, "startdate": 100, "enddate": 200})

    assert result == {"status": "accepted", "appli": 1}
    mock_store.assert_called_once()
    assert mock_send.call_args.kwargs["queue"] == "webhook_sync"


@patch("app.services.providers.withings.webhook_handler.on_connection_revoked")
def test_profile_delete_revokes_every_local_connection_for_that_account(mock_revoked: MagicMock) -> None:
    # One Withings account can back several local profiles; all lose access together.
    handler = _handler()
    handler.connection_repo = MagicMock()
    connections = [
        SimpleNamespace(user_id=uuid4(), id=uuid4(), updated_at=datetime(2026, 3, 1, tzinfo=timezone.utc)),
        SimpleNamespace(user_id=uuid4(), id=uuid4(), updated_at=datetime(2026, 3, 1, tzinfo=timezone.utc)),
    ]
    handler.connection_repo.get_all_by_provider_user_id.return_value = connections
    handler.connection_repo.disconnect.return_value = True

    result = handler.process_payload(MagicMock(), {"userid": "42", "appli": 46, "action": "delete"}, "trace")

    assert result["status"] == "revoked"
    assert handler.connection_repo.disconnect.call_count == 2
    assert mock_revoked.call_count == 2


# ---------------------------- notify reconciliation ----------------------------


def _service() -> WithingsWebhookService:
    service = WithingsWebhookService(
        connection_repo=MagicMock(), oauth=MagicMock(), default_live_sync_mode=LiveSyncMode.PULL
    )
    service.provider_settings_repo = MagicMock()
    return service


def test_register_user_subscriptions_subscribes_every_missing_appli() -> None:
    service = _service()
    with (
        patch.object(service, "_list_subscriptions", return_value=[]),
        patch.object(service, "_change_subscription", return_value={"status": "subscribed"}) as mock_change,
    ):
        results = service.sync_user(MagicMock(), uuid4(), LiveSyncMode.WEBHOOK)

    assert len(results) == len(SUBSCRIBED_APPLIS)
    assert {call.args[2] for call in mock_change.call_args_list} == {"subscribe"}


def test_register_user_subscriptions_revokes_our_own_profiles_when_switched_to_pull() -> None:
    service = _service()
    existing = [SimpleNamespace(appli=1, callbackurl=CALLBACK_URL, comment="open-wearables")]
    with (
        patch.object(service, "_list_subscriptions", return_value=existing),
        patch.object(service, "_change_subscription", return_value={"status": "revoked"}) as mock_change,
    ):
        service.sync_user(MagicMock(), uuid4(), LiveSyncMode.PULL)

    assert mock_change.call_args.args[2] == "revoke"


def test_register_user_subscriptions_leaves_profiles_registered_by_another_host_alone() -> None:
    service = _service()
    existing = [SimpleNamespace(appli=1, callbackurl="https://other.example/webhooks?token=x", comment=None)]
    with (
        patch.object(service, "_list_subscriptions", return_value=existing),
        patch.object(service, "_change_subscription") as mock_change,
    ):
        service.sync_user(MagicMock(), uuid4(), LiveSyncMode.PULL)

    mock_change.assert_not_called()


def test_register_user_subscriptions_skips_when_the_webhook_token_is_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.config.settings.withings_webhook_token", None)

    results = _service().sync_user(MagicMock(), uuid4(), LiveSyncMode.WEBHOOK)

    assert results == [{"status": "skipped", "reason": "webhook_token_unconfigured"}]


@patch("app.services.providers.withings.webhook_service.WithingsWebhookService.sync_user")
@patch("app.services.providers.withings.oauth.SessionLocal")
def test_deregister_user_revokes_only_when_it_is_the_last_link(mock_session: MagicMock, mock_sync: MagicMock) -> None:
    # Subscriptions belong to the Withings account, so a sibling profile keeps them.
    oauth = WithingsOAuth(
        user_repo=MagicMock(), connection_repo=MagicMock(), provider_name="withings", api_base_url="https://x"
    )
    user_id = uuid4()
    lookup = oauth.connection_repo.get_all_by_provider_user_id

    lookup.return_value = [SimpleNamespace(user_id=user_id), SimpleNamespace(user_id=uuid4())]
    oauth.deregister_user("at", provider_user_id="42")
    mock_sync.assert_not_called()

    lookup.return_value = [SimpleNamespace(user_id=user_id)]
    oauth.deregister_user("at", provider_user_id="42")

    assert mock_sync.call_args.args[1] == user_id
    assert mock_sync.call_args.args[2] == LiveSyncMode.PULL


def test_deregister_user_without_a_provider_user_id_does_nothing() -> None:
    oauth = WithingsOAuth(
        user_repo=MagicMock(), connection_repo=MagicMock(), provider_name="withings", api_base_url="https://x"
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
