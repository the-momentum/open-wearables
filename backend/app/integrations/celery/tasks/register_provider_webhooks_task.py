"""Celery task for registering provider webhook subscriptions.

Dispatched when a provider's live_sync_mode is switched to 'webhook' in settings.
Runs asynchronously so the settings API response is not blocked.
"""

import asyncio
from logging import getLogger

from celery import Task, shared_task

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
        results = asyncio.run(strategy.register_webhooks(callback_url))
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
