"""Celery task that emits outgoing webhook events via Svix.

Called asynchronously after data is saved to the database so the
request / ingestion path is never blocked by webhook delivery.
"""

from __future__ import annotations

from logging import getLogger
from typing import Any

from celery import shared_task

from app.database import SessionLocal
from app.services import developer_service
from app.services.outgoing_webhooks import svix as svix_service

logger = getLogger(__name__)


@shared_task(
    name="app.integrations.celery.tasks.emit_webhook_event_task.emit_webhook_event",
    bind=True,
    max_retries=2,
    default_retry_delay=5,
    acks_late=True,
)
def emit_webhook_event(
    self: Any,
    event_type: str,
    payload: dict[str, Any],
    *,
    channels: list[str] | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Send a webhook event to every developer's Svix application.

    In a single-developer self-hosted deployment this broadcasts to one
    application.  Multi-developer scoping (developer_id on User) can be
    added later to narrow the audience.
    """
    if not svix_service.is_enabled():
        logger.debug("Svix is not configured — skipping webhook dispatch for event %s", event_type)
        return {"event_type": event_type, "sent": 0, "errors": []}

    with SessionLocal() as db:
        page_size = 100
        offset = 0
        developers = []
        while True:
            batch = developer_service.crud.get_all(db, filters={}, offset=offset, limit=page_size, sort_by=None)
            developers.extend(batch)
            if len(batch) < page_size:
                break
            offset += page_size

    sent = 0
    errors: list[str] = []
    for dev in developers:
        svix_service.ensure_application(str(dev.id), dev.email)
        result = svix_service.send(
            event_type,
            str(dev.id),
            payload,
            channels=channels,
            idempotency_key=idempotency_key,
        )
        if result is not None:
            sent += 1
        else:
            errors.append(str(dev.id))

    if errors:
        exc = RuntimeError(
            f"Webhook delivery failed for {len(errors)} of {sent + len(errors)} developer(s) "
            f"[event={event_type}, failed={errors}]"
        )
        logger.error(
            "Webhook delivery failed for %d developer(s) on event %s; scheduling retry",
            len(errors),
            event_type,
        )
        raise self.retry(exc=exc)

    return {"event_type": event_type, "sent": sent, "errors": errors}
