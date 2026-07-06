"""Celery task for registering provider webhook subscriptions.

Dispatched when a provider's live_sync_mode is switched to 'webhook' in settings.
Runs asynchronously so the settings API response is not blocked.
"""

import asyncio
from logging import getLogger

from celery import Task, shared_task

from app.database import SessionLocal
from app.repositories.provider_settings_repository import ProviderSettingsRepository
from app.schemas.enums import ProviderName
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
def register_provider_webhooks(self: Task, provider: str, callback_url: str) -> dict:
    """Register webhook subscriptions for a provider via its registration API.

    Only dispatched for providers with ``webhook_registration_api=True``.
    New subscriptions are created; existing ones are skipped.
    """
    try:
        strategy = ProviderFactory().get_provider(provider)
        if strategy.webhook_service is None:
            raise NotImplementedError(f"Provider '{provider}' does not support webhook subscription management")
        results = asyncio.run(strategy.webhook_service.register_subscriptions(callback_url))
        created = sum(1 for r in results if r.get("status") == "created")
        skipped = sum(1 for r in results if r.get("status") == "skipped")
        errors = sum(1 for r in results if r.get("status") == "error")
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
            "Provider does not support webhook registration API",
            provider=provider,
            action="register_provider_webhooks_unsupported",
            error=str(exc),
        )
        return {"provider": provider, "created": 0, "skipped": 0, "errors": 1}
    except Exception as exc:
        log_structured(
            logger,
            "error",
            "Webhook registration task failed, scheduling retry",
            provider=provider,
            error=str(exc),
            attempt=self.request.retries,
            max_retries=self.max_retries,
        )
        raise self.retry(exc=exc)
