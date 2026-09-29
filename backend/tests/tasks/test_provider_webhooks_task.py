"""Tests for the live-sync mode reconciliation task.

The task is the single entry point for both directions: ``webhook`` registers
subscriptions against the callback URL, ``pull`` deletes whatever the provider
still holds.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.integrations.celery.tasks.provider_webhooks_task as task
from app.schemas.auth import LiveSyncMode
from app.schemas.responses.incoming_webhooks import WebhookOperationResult, WebhookSubscriptionStatus


def _deleted(subscription_id: str) -> WebhookOperationResult:
    return WebhookOperationResult(subscription_id=subscription_id, status=WebhookSubscriptionStatus.DELETED)


@pytest.fixture
def strategy() -> MagicMock:
    strategy = MagicMock()
    strategy.capabilities.webhook_inbound_secret = False
    strategy.webhook_service = MagicMock()
    return strategy


def _run(provider: str, mode: LiveSyncMode, strategy: MagicMock) -> Any:
    with patch.object(task.ProviderFactory, "get_provider", return_value=strategy):
        return task.reconcile_provider_webhooks.run(provider, mode)


def test_webhook_mode_registers_against_the_callback_url(strategy: MagicMock) -> None:
    """Should register subscriptions pointing at the provider's own callback route."""
    strategy.webhook_service.register_subscriptions = AsyncMock(return_value=[{"status": "created"}])

    result = _run("oura", LiveSyncMode.WEBHOOK, strategy)

    callback_url = strategy.webhook_service.register_subscriptions.await_args[0][0]
    assert callback_url.endswith("/providers/oura/webhooks")
    assert result == {"provider": "oura", "created": 1, "skipped": 0, "errors": 0}


def test_pull_mode_deletes_subscriptions(strategy: MagicMock) -> None:
    """Should delete the subscriptions the provider still holds."""
    strategy.webhook_service.deregister_subscriptions = AsyncMock(return_value=[_deleted("sub-1")])

    result = _run("oura", LiveSyncMode.PULL, strategy)

    strategy.webhook_service.deregister_subscriptions.assert_awaited_once()
    strategy.webhook_service.register_subscriptions.assert_not_called()
    assert result == {"provider": "oura", "deleted": 1, "errors": 0}


def test_pull_mode_retries_when_a_delete_fails(strategy: MagicMock) -> None:
    """Should retry rather than report success: a surviving subscription keeps delivering."""
    strategy.webhook_service.deregister_subscriptions = AsyncMock(
        return_value=[
            _deleted("sub-1"),
            WebhookOperationResult(subscription_id="sub-2", status=WebhookSubscriptionStatus.ERROR, error="boom"),
        ]
    )

    with pytest.raises(RuntimeError, match="failed for 1 of 2"):
        _run("oura", LiveSyncMode.PULL, strategy)


def test_provider_without_webhook_service_is_reported_not_retried(strategy: MagicMock) -> None:
    """Should return an error result instead of retrying a provider that cannot reconcile."""
    strategy.webhook_service = None

    result = _run("apple", LiveSyncMode.PULL, strategy)

    assert result["errors"] == 1
