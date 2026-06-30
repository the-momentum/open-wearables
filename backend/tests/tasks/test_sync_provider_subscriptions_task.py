"""Tests for the generic per-user subscription live-mode sync task.

It resolves the provider's per-user task name (subscribe for WEBHOOK, revoke for
PULL) and fans out one task per active connection on the webhook_sync queue.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.integrations.celery.tasks.sync_provider_subscriptions_task import sync_provider_subscriptions
from app.schemas.auth import LiveSyncMode

_SUBSCRIBE = "app.integrations.celery.tasks.withings.subscribe_task.subscribe_withings_user"
_REVOKE = "app.integrations.celery.tasks.withings.subscribe_task.revoke_withings_user"


def _run(mode: LiveSyncMode, task_name: str | None, user_ids: list) -> tuple[dict, MagicMock]:
    strategy = MagicMock()
    strategy.live_sync_subscription_task.return_value = task_name
    strategy.connection_repo.get_all_active_by_provider.return_value = [MagicMock(user_id=u) for u in user_ids]
    with (
        patch("app.integrations.celery.tasks.sync_provider_subscriptions_task.ProviderFactory") as factory,
        patch("app.integrations.celery.tasks.sync_provider_subscriptions_task.SessionLocal") as session_local,
        patch("app.integrations.celery.tasks.sync_provider_subscriptions_task.celery_app") as celery,
    ):
        factory.return_value.get_provider.return_value = strategy
        session_local.return_value.__enter__ = MagicMock(return_value=MagicMock())
        session_local.return_value.__exit__ = MagicMock(return_value=False)
        result = sync_provider_subscriptions.apply(args=["withings", mode.value]).get()
        return result, celery


def test_webhook_mode_fans_out_subscribe_per_active_user() -> None:
    u1, u2 = uuid4(), uuid4()
    result, celery = _run(LiveSyncMode.WEBHOOK, _SUBSCRIBE, [u1, u2])

    assert result["dispatched"] == 2
    assert celery.send_task.call_count == 2
    for call in celery.send_task.call_args_list:
        assert call.args[0] == _SUBSCRIBE
        assert call.kwargs["queue"] == "webhook_sync"
    dispatched_users = {call.kwargs["args"][0] for call in celery.send_task.call_args_list}
    assert dispatched_users == {str(u1), str(u2)}


def test_pull_mode_fans_out_revoke_per_active_user() -> None:
    result, celery = _run(LiveSyncMode.PULL, _REVOKE, [uuid4()])

    assert result["dispatched"] == 1
    assert celery.send_task.call_args.args[0] == _REVOKE


def test_no_task_for_mode_dispatches_nothing() -> None:
    result, celery = _run(LiveSyncMode.PULL, None, [uuid4(), uuid4()])

    assert result["dispatched"] == 0
    celery.send_task.assert_not_called()
