"""Webhook events of extensions: an extension emits the event types its ``webhook_event_types()`` declares."""

from typing import Any
from uuid import UUID

from app.extensions import collect_webhook_event_types
from app.services.outgoing_webhooks.events import on_extension_event
from app.utils.structured_logging import get_logger

logger = get_logger(__name__)


def emit(
    event_type: str, data: dict[str, Any], *, user_id: UUID | None = None, idempotency_key: str | None = None
) -> None:
    """Queue a declared event of the extension, like the core's; call it after the commit. With ``user_id`` it goes
    on that user's channel and carries ``data.user_id``. An undeclared type is logged and dropped."""
    if event_type not in collect_webhook_event_types():
        logger.error("Undeclared extension webhook event type, not sent", event_type=event_type)
        return
    on_extension_event(event_type, data, user_id=user_id, idempotency_key=idempotency_key)
