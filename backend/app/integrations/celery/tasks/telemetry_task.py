"""Anonymous usage telemetry Celery task.

Runs hourly via beat (plus once on worker startup) and delivers a ping only
when one is due - see TelemetryService for the debounce rules. Best-effort by
design: a failed delivery is logged and retried naturally on the next hourly
run, never raised.
"""

from logging import getLogger

from celery import shared_task

from app.database import SessionLocal
from app.services.telemetry_service import telemetry_service

logger = getLogger(__name__)


@shared_task(
    name="app.integrations.celery.tasks.telemetry_task.send_telemetry_ping",
    soft_time_limit=120,
    time_limit=180,
)
def send_telemetry_ping(event: str = "daily") -> str:
    with SessionLocal() as db:
        try:
            return telemetry_service.send_ping(db, event=event)
        except Exception:
            logger.warning("Telemetry ping delivery failed (event=%s)", event, exc_info=True)
            return "failed"
