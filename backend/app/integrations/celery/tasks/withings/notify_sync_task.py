"""Celery task for reconciling one Withings connection's Notify subscriptions.

Withings subscriptions are created with each connection's own access token, so
the unit of work is a connection, not the provider: one Notify List plus a
subscribe or revoke per appli. Provider-scoped for the same reason — no other
provider has per-user subscriptions, so this stays out of the shared
``reconcile_provider_webhooks`` task instead of putting a Withings concept on
``BaseWebhookService``.

Dispatched by the provider-wide fan-out and by the OAuth callback, which must
reconcile a single new connection rather than every existing one.
"""

from logging import getLogger
from uuid import UUID

from celery import Task, shared_task

from app.database import SessionLocal
from app.services.providers.factory import ProviderFactory
from app.services.providers.withings.webhook_service import WithingsWebhookService
from app.utils.structured_logging import log_structured

logger = getLogger(__name__)


@shared_task(
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
    max_retries=3,
    default_retry_delay=60,
)
def sync_user_subscriptions(self: Task, user_id: str) -> dict:
    """Bring one connection's subscriptions in line with the configured live-sync mode.

    The service lists first and changes only the gap, so a redelivery after a
    lost worker is safe, and a mode of ``pull`` revokes rather than creates.
    """
    # Parsed up front: a malformed id and a mis-wired strategy are both permanent.
    user_uuid = UUID(user_id)
    service = ProviderFactory().get_provider("withings").webhook_service
    if not isinstance(service, WithingsWebhookService):
        raise RuntimeError("Withings strategy is not wired with its notify service")

    try:
        with SessionLocal() as db:
            results = service.reconcile_user(db, user_uuid)
    except Exception as exc:
        log_structured(
            logger,
            "error",
            "Withings user subscription sync failed, scheduling retry",
            provider="withings",
            user_id=user_id,
            error=str(exc),
            attempt=self.request.retries,
            max_retries=self.max_retries,
        )
        raise self.retry(exc=exc)

    failed = [result for result in results if result.get("status") == "error"]
    if failed:
        log_structured(
            logger,
            "error",
            "Withings user subscription sync had failures",
            provider="withings",
            user_id=user_id,
            failed_items=failed,
            attempt=self.request.retries,
            max_retries=self.max_retries,
        )
        # Attach the cause; a bare MaxRetriesExceededError would lose the failed items.
        raise self.retry(exc=RuntimeError(f"Withings subscription sync failed for user {user_id}: {failed}"))

    log_structured(
        logger,
        "info",
        "Withings user subscriptions synced",
        provider="withings",
        user_id=user_id,
        results=results,
    )
    return {"provider": "withings", "user_id": user_id, "results": results}
