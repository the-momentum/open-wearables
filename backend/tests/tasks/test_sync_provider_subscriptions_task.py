"""Tests for generic user-scoped subscription reconciliation tasks."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.integrations.celery.tasks.register_provider_webhooks_task import (
    register_provider_webhooks,
    sync_provider_user_subscription,
)
from app.schemas.auth import LiveSyncMode
from app.services.providers.base_strategy import ProviderCapabilities

_SYNC_USER = "app.integrations.celery.tasks.register_provider_webhooks_task.sync_provider_user_subscription"


def test_fanout_dispatches_one_reconciliation_per_active_user() -> None:
    user_ids = [uuid4(), uuid4()]
    strategy = MagicMock()
    strategy.capabilities = ProviderCapabilities(
        rest_pull=True,
        webhook_ping=True,
        webhook_per_user_subscriptions=True,
    )
    strategy.webhook_service = MagicMock()
    strategy.connection_repo.get_all_active_by_provider.return_value = [
        MagicMock(user_id=user_id) for user_id in user_ids
    ]

    with (
        patch("app.integrations.celery.tasks.register_provider_webhooks_task.ProviderFactory") as factory,
        patch("app.integrations.celery.tasks.register_provider_webhooks_task.SessionLocal") as session_local,
        patch("app.integrations.celery.tasks.register_provider_webhooks_task.celery_app") as celery,
    ):
        factory.return_value.get_provider.return_value = strategy
        session_local.return_value.__enter__ = MagicMock(return_value=MagicMock())
        session_local.return_value.__exit__ = MagicMock(return_value=False)
        result = register_provider_webhooks.apply(args=["withings"]).get()

    assert result == {"provider": "withings", "dispatched": 2}
    assert celery.send_task.call_count == 2
    dispatched_user_ids = {call.kwargs["args"][1] for call in celery.send_task.call_args_list}
    assert dispatched_user_ids == {str(user_id) for user_id in user_ids}
    assert all(call.args[0] == _SYNC_USER for call in celery.send_task.call_args_list)


def test_fanout_skips_provider_without_user_scoped_service() -> None:
    strategy = MagicMock(webhook_service=None)
    strategy.capabilities = ProviderCapabilities()
    with patch("app.integrations.celery.tasks.register_provider_webhooks_task.ProviderFactory") as factory:
        factory.return_value.get_provider.return_value = strategy
        result = register_provider_webhooks.apply(args=["oura"]).get()
    assert result == {"provider": "oura", "dispatched": 0}


def test_application_registration_uses_same_entry_task() -> None:
    service = MagicMock()
    service.register_subscriptions = AsyncMock(
        return_value=[
            {"status": "created"},
            {"status": "skipped"},
            {"status": "error"},
        ]
    )
    strategy = MagicMock(webhook_service=service)
    strategy.capabilities = ProviderCapabilities(webhook_registration_api=True)

    with patch("app.integrations.celery.tasks.register_provider_webhooks_task.ProviderFactory") as factory:
        factory.return_value.get_provider.return_value = strategy
        result = register_provider_webhooks.apply(args=["oura", "https://example.test/webhook"]).get()

    service.register_subscriptions.assert_awaited_once_with("https://example.test/webhook")
    assert result == {"provider": "oura", "created": 1, "skipped": 1, "errors": 1}


@pytest.mark.parametrize("mode", [LiveSyncMode.WEBHOOK, LiveSyncMode.PULL])
def test_user_reconciliation_reads_latest_mode(mode: LiveSyncMode) -> None:
    user_id = uuid4()
    service = MagicMock()
    service.sync_user.return_value = [{"appli": 1, "status": "ok"}]
    strategy = MagicMock(webhook_service=service)
    strategy.effective_live_sync_mode.return_value = mode
    db = MagicMock()

    with (
        patch("app.integrations.celery.tasks.register_provider_webhooks_task.ProviderFactory") as factory,
        patch("app.integrations.celery.tasks.register_provider_webhooks_task.SessionLocal") as session_local,
    ):
        factory.return_value.get_provider.return_value = strategy
        session_local.return_value.__enter__ = MagicMock(return_value=db)
        session_local.return_value.__exit__ = MagicMock(return_value=False)
        result = sync_provider_user_subscription.apply(args=["withings", str(user_id)]).get()

    service.sync_user.assert_called_once_with(db, user_id, mode)
    assert result["mode"] == mode.value


def test_user_reconciliation_retries_partial_failure() -> None:
    service = MagicMock()
    service.sync_user.return_value = [
        {"appli": 1, "status": "subscribed"},
        {"appli": 44, "status": "error", "error": "boom"},
    ]
    strategy = MagicMock(webhook_service=service)
    strategy.effective_live_sync_mode.return_value = LiveSyncMode.WEBHOOK

    with (
        patch("app.integrations.celery.tasks.register_provider_webhooks_task.ProviderFactory") as factory,
        patch("app.integrations.celery.tasks.register_provider_webhooks_task.SessionLocal") as session_local,
        patch.object(sync_provider_user_subscription, "retry", side_effect=Exception("retry-called")),
    ):
        factory.return_value.get_provider.return_value = strategy
        session_local.return_value.__enter__ = MagicMock(return_value=MagicMock())
        session_local.return_value.__exit__ = MagicMock(return_value=False)
        with pytest.raises(Exception, match="retry-called"):
            sync_provider_user_subscription.apply(args=["withings", str(uuid4())]).get()
