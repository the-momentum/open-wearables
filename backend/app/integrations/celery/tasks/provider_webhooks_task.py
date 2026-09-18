"""Celery tasks for reconciling provider webhook subscriptions.

Dispatched by ``BaseProviderStrategy.apply_live_sync_mode`` when a provider's
live_sync_mode is switched in settings. Runs asynchronously so the settings API
response is not blocked. Providers with per-user subscriptions fan out from
their own webhook service into ``register_user_webhooks``, one task per active
connection, in both directions.
"""

import asyncio
from logging import getLogger
from typing import Any
from uuid import UUID

from celery import Task, shared_task

from app.config import settings
from app.database import SessionLocal
from app.repositories.provider_settings_repository import ProviderSettingsRepository
from app.schemas.auth import LiveSyncMode
from app.schemas.enums import ProviderName
from app.services.providers.factory import ProviderFactory
from app.utils.structured_logging import log_structured

logger = getLogger(__name__)


def _status(result: Any) -> str:
    """Read the status of one result entry, which providers report as a dict or a model."""
    return result["status"] if isinstance(result, dict) else str(result.status)


@shared_task(
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
    max_retries=3,
    default_retry_delay=60,
)
def reconcile_provider_webhooks(self: Task, provider: str, mode: str) -> dict:
    """Bring a provider's webhook subscriptions in line with its new live-sync mode.

    Only dispatched for providers with ``webhook_registration_api=True``. On
    ``webhook`` new subscriptions are created and existing ones skipped; on
    ``pull`` every subscription the provider holds is deleted.
    """
    try:
        strategy = ProviderFactory().get_provider(provider)
        if strategy.webhook_service is None:
            raise NotImplementedError(f"Provider '{provider}' does not support webhook subscription management")

        if LiveSyncMode(mode) == LiveSyncMode.PULL:
            results = asyncio.run(strategy.webhook_service.deregister_subscriptions())
            errors = sum(1 for result in results if _status(result) == "error")
            log_structured(
                logger,
                "error" if errors else "info",
                "Webhook subscriptions deregistered",
                provider=provider,
                action="deregister_provider_webhooks_complete",
                deleted=len(results) - errors,
                errors=errors,
            )
            return {"provider": provider, "deleted": len(results) - errors, "errors": errors}

        callback_url = f"{settings.api_base_url}{settings.api_v1}/providers/{provider}/webhooks"
        results = asyncio.run(strategy.webhook_service.register_subscriptions(callback_url))
        created = sum(1 for result in results if _status(result) == "created")
        skipped = sum(1 for result in results if _status(result) == "skipped")
        errors = sum(1 for result in results if _status(result) == "error")
        log_structured(
            logger,
            "info",
            "Webhook subscriptions registered",
            provider=provider,
            action="register_provider_webhooks_complete",
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

    except (ValueError, NotImplementedError) as exc:
        log_structured(
            logger,
            "error",
            "Provider does not support webhook subscription management",
            provider=provider,
            action="reconcile_provider_webhooks_unsupported",
            error=str(exc),
        )
        return {"provider": provider, "created": 0, "skipped": 0, "errors": 1}
    except Exception as exc:
        log_structured(
            logger,
            "error",
            "Webhook reconciliation task failed, scheduling retry",
            provider=provider,
            error=str(exc),
            attempt=self.request.retries,
            max_retries=self.max_retries,
        )
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
    max_retries=3,
    default_retry_delay=60,
)
def register_user_webhooks(self: Task, provider: str, user_id: str) -> dict:
    """Register (or revoke) one user's subscriptions per the provider's live-sync mode.

    Split from ``reconcile_provider_webhooks`` rather than folded into it: each
    user costs its own list-plus-subscribe round trips, so one task per user
    keeps a failure and its retry scoped to that user instead of redoing every
    connection. It is also what the OAuth callback enqueues for a single new
    connection, which must not fan out over the whole provider.

    The provider lists first and changes only the gap, so a redelivery after a
    lost worker is safe.
    """
    strategy = ProviderFactory().get_provider(provider)
    # Per-user registration is a provider-local operation, not part of
    # BaseWebhookService, so it is resolved the same way the webhook router
    # resolves handle_probe.
    register = getattr(strategy.webhook_service, "register_user_subscriptions", None)
    if register is None:
        raise NotImplementedError(f"Provider '{provider}' does not manage per-user webhook subscriptions")

    with SessionLocal() as db:
        results = register(db, UUID(user_id))

    failed = [result for result in results if result.get("status") == "error"]
    if failed:
        log_structured(
            logger,
            "error",
            "Provider user webhook registration had failures",
            provider=provider,
            user_id=user_id,
            failed_items=failed,
            attempt=self.request.retries,
            max_retries=self.max_retries,
        )
        # Attach the cause; a bare MaxRetriesExceededError would lose the failed items.
        raise self.retry(exc=RuntimeError(f"{provider} user webhook registration failed for user {user_id}: {failed}"))

    log_structured(
        logger,
        "info",
        "Provider user webhooks registered",
        provider=provider,
        user_id=user_id,
        results=results,
    )
    return {"provider": provider, "user_id": user_id, "results": results}
