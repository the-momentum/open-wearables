"""Celery task that releases a deleted user's Open Wearables Connect app seat.

Scheduled by ``UserService.delete``. Runs in the background so a license server outage
never blocks the deletion; it retries, and a seat not released at all expires after
30 days without heartbeats anyway.
"""

from typing import Any
from uuid import UUID

from celery import shared_task

from app.constants.celery_tasks import CeleryTask
from app.database import SessionLocal
from app.integrations.license_server import LicenseServerUnavailableError
from app.services.app_registration_service import app_registration_service
from app.utils.structured_logging import get_logger

logger = get_logger(__name__)


@shared_task(
    name=CeleryTask.RELEASE_APP_SEAT,
    bind=True,
    max_retries=8,
    default_retry_delay=300,
    acks_late=True,
)
def release_app_seat(self: Any, user_id: str) -> dict[str, str]:
    try:
        with SessionLocal() as db:
            app_registration_service.release_seat(db, UUID(user_id))
    except LicenseServerUnavailableError as exc:
        raise self.retry(exc=exc)
    logger.info("Released app seat of deleted user", user_id=user_id)
    return {"user_id": user_id}
