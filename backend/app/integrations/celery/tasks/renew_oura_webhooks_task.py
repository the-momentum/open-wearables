"""Celery task for renewing Oura webhook subscriptions.

Oura subscriptions expire after 90 days. This task runs monthly to renew
all active subscriptions well before they expire.
"""

import asyncio

from celery import Task, shared_task

from app.constants.celery_tasks import CeleryTask
from app.services.providers.oura.webhook_service import oura_webhook_service
from app.utils.structured_logging import get_logger

logger = get_logger(__name__)


@shared_task(
    name=CeleryTask.RENEW_OURA_WEBHOOKS,
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
    max_retries=3,
    default_retry_delay=3600,  # retry after 1 hour on failure
)
def renew_oura_webhooks(self: Task) -> dict:
    """Renew all active Oura webhook subscriptions."""
    try:
        results = asyncio.run(oura_webhook_service.renew_subscriptions())
        renewed = sum(1 for r in results if r.get("status") == "renewed")
        errors = sum(1 for r in results if r.get("status") == "error")
        logger.info(
            "Oura webhook subscriptions renewed",
            action="renew_oura_webhooks_complete",
            renewed=renewed,
            errors=errors,
        )
        return {"renewed": renewed, "errors": errors}

    except Exception as exc:
        logger.error(
            "Oura webhook renewal task failed, scheduling retry",
            error=str(exc),
            attempt=self.request.retries,
            max_retries=self.max_retries,
        )
        raise self.retry(exc=exc)
