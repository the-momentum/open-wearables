"""Celery task for applying a live-sync-mode change to a per-user-subscription provider.

Dispatched when such a provider's ``live_sync_mode`` is switched in settings.
Fans out one per-user subscribe/revoke task per active connection, so each user's
notify call retries in isolation instead of one bulk loop failing as a unit.

Only dispatched for providers with ``webhook_per_user_subscriptions=True``.
"""

from logging import getLogger

from celery import Task, shared_task
from celery import current_app as celery_app

from app.database import SessionLocal
from app.schemas.auth import LiveSyncMode
from app.services.providers.factory import ProviderFactory
from app.utils.structured_logging import log_structured

logger = getLogger(__name__)


@shared_task(
    bind=True,
    name="app.integrations.celery.tasks.sync_provider_subscriptions_task.sync_provider_subscriptions",
)
def sync_provider_subscriptions(self: Task, provider: str, mode: str) -> dict:
    """Fan out the per-user subscribe/revoke task to every active connection."""
    strategy = ProviderFactory().get_provider(provider)
    task_name = strategy.live_sync_subscription_task(LiveSyncMode(mode))
    if task_name is None:
        return {"provider": provider, "mode": mode, "dispatched": 0}

    with SessionLocal() as db:
        user_ids = [str(c.user_id) for c in strategy.connection_repo.get_all_active_by_provider(db, provider)]

    for user_id in user_ids:
        celery_app.send_task(task_name, args=[user_id], queue="webhook_sync")

    log_structured(
        logger,
        "info",
        "Provider subscription sync fanned out",
        provider=provider,
        mode=mode,
        task=task_name,
        dispatched=len(user_ids),
    )
    return {"provider": provider, "mode": mode, "dispatched": len(user_ids)}
