"""Celery task for reconciling a provider's webhook subscriptions.

Dispatched by ``BaseProviderStrategy.apply_live_sync_mode`` when a provider's
live_sync_mode is switched in settings. Runs asynchronously so the settings API
response is not blocked. A provider whose subscriptions are per connection fans
out from its own webhook service into its own task, in both directions.
"""

import asyncio
from logging import getLogger

from celery import Task, shared_task

from app.config import settings
from app.database import SessionLocal
from app.repositories.provider_settings_repository import ProviderSettingsRepository
from app.schemas.auth import LiveSyncMode
from app.schemas.enums import ProviderName
from app.schemas.responses.incoming_webhooks import WebhookSubscriptionStatus
from app.services.providers.factory import ProviderFactory
from app.utils.structured_logging import log_structured

logger = getLogger(__name__)


@shared_task(
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
    max_retries=3,
    default_retry_delay=60,
)
def reconcile_provider_webhooks(self: Task, provider: str, mode: str) -> dict:
    """Bring a provider's webhook subscriptions in line with a new live-sync mode.

    Only dispatched for providers with ``webhook_registration_api=True``. On
    ``webhook`` new subscriptions are created and existing ones skipped; on
    ``pull`` every subscription the provider holds is deleted. ``mode`` arrives
    as the bare string value, since Celery serializes the StrEnum.
    """
    try:
        strategy = ProviderFactory().get_provider(provider)
        if strategy.webhook_service is None:
            raise NotImplementedError(f"Provider '{provider}' does not support webhook subscription management")

        if mode == LiveSyncMode.PULL:
            results = asyncio.run(strategy.webhook_service.deregister_subscriptions())
            deleted = sum(1 for result in results if result.status == WebhookSubscriptionStatus.DELETED)
            errors = sum(1 for result in results if result.status == WebhookSubscriptionStatus.ERROR)
            log_structured(
                logger,
                "error" if errors else "info",
                "Webhook subscriptions deregistered",
                provider=provider,
                action="deregister_provider_webhooks_complete",
                deleted=deleted,
                errors=errors,
            )
            # Raised, not retried inline: self.retry() raises Retry, which the handler catches.
            if errors:
                raise RuntimeError(f"{provider} webhook deregistration failed for {errors} of {len(results)}")
            return {"provider": provider, "deleted": deleted, "errors": errors}

        callback_url = f"{settings.api_base_url}{settings.api_v1}/providers/{provider}/webhooks"
        results = asyncio.run(strategy.webhook_service.register_subscriptions(callback_url))
        created = sum(1 for result in results if result.get("status") == "created")
        skipped = sum(1 for result in results if result.get("status") == "skipped")
        errors = sum(1 for result in results if result.get("status") == "error")
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

        if errors:
            raise RuntimeError(f"{provider} webhook registration failed for {errors} of {len(results)}")
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
