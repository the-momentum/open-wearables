"""Celery tasks for reconciling provider webhook subscriptions.

The established entry task handles both provider ownership models: one
application-level registration, or a fan-out over user-owned subscriptions.
Each user child reads the latest stored mode before acting, so rapid mode
changes converge on current state and users retry independently.
"""

import asyncio
from logging import getLogger
from uuid import UUID

from celery import Task, shared_task
from celery import current_app as celery_app

from app.database import SessionLocal
from app.repositories.provider_settings_repository import ProviderSettingsRepository
from app.schemas.enums import ProviderName
from app.services.providers.base_strategy import BaseProviderStrategy
from app.services.providers.factory import ProviderFactory
from app.utils.structured_logging import log_structured

logger = getLogger(__name__)

_SYNC_PROVIDER_USER_SUBSCRIPTION_TASK = (
    "app.integrations.celery.tasks.register_provider_webhooks_task.sync_provider_user_subscription"
)


def _fan_out_user_subscriptions(strategy: BaseProviderStrategy, provider: str) -> dict:
    if strategy.webhook_service is None:
        raise NotImplementedError(f"Provider '{provider}' has no webhook subscription service")

    with SessionLocal() as db:
        user_ids = [str(c.user_id) for c in strategy.connection_repo.get_all_active_by_provider(db, provider)]

    for user_id in user_ids:
        celery_app.send_task(_SYNC_PROVIDER_USER_SUBSCRIPTION_TASK, args=[provider, user_id], queue="webhook_sync")

    log_structured(
        logger,
        "info",
        "Provider subscription sync fanned out",
        provider=provider,
        dispatched=len(user_ids),
    )
    return {"provider": provider, "dispatched": len(user_ids)}


def _sync_application_subscriptions(
    strategy: BaseProviderStrategy,
    provider: str,
    callback_url: str | None,
) -> dict:
    if strategy.webhook_service is None or callback_url is None:
        raise NotImplementedError(f"Provider '{provider}' has no application webhook registration service")

    results = asyncio.run(strategy.webhook_service.register_subscriptions(callback_url))
    created = sum(1 for result in results if result.get("status") == "created")
    skipped = sum(1 for result in results if result.get("status") == "skipped")
    errors = sum(1 for result in results if result.get("status") == "error")
    log_structured(
        logger,
        "info",
        "Provider webhook subscriptions reconciled",
        provider=provider,
        created=created,
        skipped=skipped,
        errors=errors,
    )

    if skipped and strategy.capabilities.webhook_inbound_secret:
        with SessionLocal() as db:
            secret = ProviderSettingsRepository().get_webhook_secret(db, ProviderName(provider))
        if not secret:
            log_structured(
                logger,
                "warning",
                "Webhook skipped but no inbound secret stored — delete and re-register to obtain a new secret",
                provider=provider,
                action="webhook_inbound_secret_missing",
            )

    return {"provider": provider, "created": created, "skipped": skipped, "errors": errors}


@shared_task(
    bind=True,
    name="app.integrations.celery.tasks.register_provider_webhooks_task.register_provider_webhooks",
    acks_late=True,
    reject_on_worker_lost=True,
    max_retries=3,
    default_retry_delay=60,
)
def register_provider_webhooks(self: Task, provider: str, callback_url: str | None = None) -> dict:
    """Reconcile subscriptions using the provider's declared ownership model."""
    try:
        strategy = ProviderFactory().get_provider(provider)
        capabilities = strategy.capabilities
        if capabilities.webhook_per_user_subscriptions:
            return _fan_out_user_subscriptions(strategy, provider)
        if capabilities.webhook_registration_api:
            return _sync_application_subscriptions(strategy, provider, callback_url)
        return {"provider": provider, "dispatched": 0}
    except (ValueError, NotImplementedError) as exc:
        log_structured(
            logger,
            "error",
            "Provider does not support webhook subscription management",
            provider=provider,
            error=str(exc),
        )
        return {"provider": provider, "created": 0, "skipped": 0, "errors": 1}
    except Exception as exc:
        log_structured(
            logger,
            "error",
            "Provider subscription reconciliation failed, scheduling retry",
            provider=provider,
            error=str(exc),
            attempt=self.request.retries,
            max_retries=self.max_retries,
        )
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    name=_SYNC_PROVIDER_USER_SUBSCRIPTION_TASK,
    max_retries=3,
    default_retry_delay=60,
)
def sync_provider_user_subscription(self: Task, provider: str, user_id: str) -> dict:
    """Reconcile one user's subscriptions with the provider's current mode."""
    strategy = ProviderFactory().get_provider(provider)
    service = strategy.webhook_service
    if service is None:
        raise NotImplementedError(f"Provider '{provider}' does not manage per-user webhook subscriptions")

    with SessionLocal() as db:
        mode = strategy.effective_live_sync_mode(db)
        if mode is None:
            return {"provider": provider, "user_id": user_id, "mode": None, "results": []}
        results = service.sync_user(db, UUID(user_id), mode)

    failed = [result for result in results if result.get("status") == "error"]
    if failed:
        log_structured(
            logger,
            "error",
            "Provider user subscription reconciliation had failures",
            provider=provider,
            user_id=user_id,
            mode=mode.value,
            failed_items=failed,
            attempt=self.request.retries,
            max_retries=self.max_retries,
        )
        raise self.retry()

    log_structured(
        logger,
        "info",
        "Provider user subscriptions reconciled",
        provider=provider,
        user_id=user_id,
        mode=mode.value,
        results=results,
    )
    return {"provider": provider, "user_id": user_id, "mode": mode.value, "results": results}
