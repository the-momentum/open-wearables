"""Celery task for processing Garmin PUSH webhook payloads.

The webhook endpoint (GarminWebhookHandler.dispatch) returns 200 immediately
and delegates all work here.  Processing logic lives in
GarminWebhookHandler.process_payload — this task is only a thin async wrapper
that provides reliability guarantees (acks_late, retries, dedicated queue).
"""

import contextlib
from logging import getLogger
from typing import Any, cast

from celery import Task, shared_task

from app.database import SessionLocal
from app.services.providers.garmin.strategy import GarminStrategy
from app.services.providers.garmin.webhook_handler import GarminWebhookHandler
from app.utils.structured_logging import log_structured

logger = getLogger(__name__)

GARMIN_SYNC_QUEUE = "garmin_sync"


@shared_task(
    bind=True,
    queue=GARMIN_SYNC_QUEUE,
    max_retries=2,
    default_retry_delay=60,
    acks_late=True,
    reject_on_worker_lost=True,
)
def process_push(self: Task, payload: dict[str, Any], request_trace_id: str) -> dict[str, Any]:
    """Process a Garmin PUSH webhook payload.

    Instantiates GarminStrategy (and its GarminWebhookHandler) then calls
    process_payload() with a fresh DB session.  Retries up to 2 times on
    unexpected infrastructure errors.
    """
    db = SessionLocal()
    try:
        strategy = GarminStrategy()
        handler = cast(GarminWebhookHandler, strategy.webhooks)
        return handler.process_payload(db, payload, request_trace_id)
    except Exception as exc:
        log_structured(
            logger,
            "error",
            "Garmin webhook task failed, scheduling retry",
            provider="garmin",
            trace_id=request_trace_id,
            error=str(exc),
            attempt=self.request.retries,
            max_retries=self.max_retries,
        )
        with contextlib.suppress(Exception):
            db.rollback()
        raise self.retry(exc=exc)
    finally:
        db.close()
