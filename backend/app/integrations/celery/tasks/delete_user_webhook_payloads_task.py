"""Celery task that deletes the outgoing webhook payloads of a deleted user from Svix.

Scheduled by ``UserService.delete`` once the user's rows are gone, so the
health data carried in their webhook payloads does not outlive the deletion
in Svix's message store.
"""

from __future__ import annotations

from logging import getLogger
from typing import Any
from uuid import UUID

from celery import shared_task
from svix.api.errors.http_error import HttpError

from app.database import SessionLocal
from app.services import developer_service
from app.services.outgoing_webhooks import svix as svix_service
from app.utils.sentry_helpers import log_and_capture_error
from app.utils.structured_logging import log_structured

logger = getLogger(__name__)


def _load_developer_ids() -> list[str]:
    """Return every developer ID; each one is also that developer's Svix application UID."""
    with SessionLocal() as db:
        page_size = 100
        offset = 0
        developer_ids: list[str] = []
        while True:
            batch = developer_service.crud.get_all(db, filters={}, offset=offset, limit=page_size, sort_by=None)
            developer_ids.extend(str(dev.id) for dev in batch)
            if len(batch) < page_size:
                return developer_ids
            offset += page_size


@shared_task(
    name="app.integrations.celery.tasks.delete_user_webhook_payloads_task.delete_user_webhook_payloads",
    bind=True,
    max_retries=5,
    default_retry_delay=60,
    acks_late=True,
)
def delete_user_webhook_payloads(self: Any, user_id: str) -> dict[str, Any]:
    """Delete the user's message payloads in every developer's Svix application.

    Messages are found through the ``user.{user_id}`` channel every OW message carries.
    A failure in any application retries the whole task; deleting a payload twice is harmless.
    """
    if not svix_service.is_enabled():
        return {"user_id": user_id, "deleted": 0, "errors": []}

    try:
        developer_ids = _load_developer_ids()
    except Exception as exc:
        raise self.retry(exc=exc)

    deleted = 0
    errors: list[str] = []
    for app_id in developer_ids:
        try:
            deleted += svix_service.delete_user_message_payloads(app_id, UUID(user_id))
        except Exception as exc:
            if isinstance(exc, HttpError) and exc.status_code == 404:
                # Application never created in Svix (it is created lazily on first emit).
                continue
            log_and_capture_error(
                exc,
                logger,
                "Failed to delete webhook payloads of deleted user",
                extra={"user_id": user_id, "app_id": app_id, "error": str(exc)},
            )
            errors.append(app_id)

    if errors:
        raise self.retry(
            exc=RuntimeError(f"Webhook payload deletion failed for user {user_id} in app(s) {errors}"),
        )

    log_structured(logger, "info", "Deleted webhook payloads of deleted user", user_id=user_id, deleted=deleted)
    return {"user_id": user_id, "deleted": deleted, "errors": errors}
