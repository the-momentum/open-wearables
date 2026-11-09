"""Webhook events of extensions: an extension emits the event types its ``webhook_event_types()`` declares."""

from typing import Any
from uuid import UUID

from app.extensions import collect_webhook_event_types
from app.utils.structured_logging import get_logger

logger = get_logger(__name__)


def emit(
    event_type: str, data: dict[str, Any], *, user_id: UUID | None = None, idempotency_key: str | None = None
) -> None:
    """Queue an extension's event for every developer's Svix application, as the core's own events go; call it after
    the database commit. ``user_id`` puts it on that user's channel, so endpoints filtered by user get it, and into
    ``data`` as ``user_id``, since the channel isn't delivered to the receiver. Never raises: an undeclared type is
    logged and dropped, and the core drops any event while Svix is off or the broker is down."""
    if event_type not in collect_webhook_event_types():
        logger.error("Undeclared extension webhook event type, not sent", event_type=event_type)
        return
    # Imported here: the outgoing webhooks services pull in much of the app, which imports app.extensions
    from app.services.outgoing_webhooks.events import on_extension_event

    on_extension_event(event_type, data, user_id=user_id, idempotency_key=idempotency_key)
