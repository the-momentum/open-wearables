"""Daily data lifecycle Celery task.

Runs once per day (via beat schedule) to:
1. Roll the days whose samples or events changed up into open_wearables day and session aggregates.
2. Delete samples older than delete_after_days, rolled up first.

Both are configured by the admin via archival_settings.
"""

from logging import getLogger

from celery import shared_task

from app.config import settings
from app.constants.celery_tasks import CeleryTask
from app.database import SessionLocal
from app.integrations.redis_client import get_redis_client
from app.services.archival_service import archival_service

logger = getLogger(__name__)

_ROLLUP_LOCK_KEY = "series_rollup:lock"
# Longer than the task may run, so a killed worker cannot hold the lock for good.
_ROLLUP_LOCK_TTL_SECONDS = 180


@shared_task(name=CeleryTask.ROLL_UP_QUEUED_DAYS, soft_time_limit=120, time_limit=150)
def roll_up_queued_days() -> dict:
    """Roll up the days whose samples or events changed, every 15 minutes, never two runs at once."""
    if not settings.data_lifecycle_enabled:
        return {"skipped": "data_lifecycle_disabled"}
    client = get_redis_client()
    if not client.set(_ROLLUP_LOCK_KEY, "1", nx=True, ex=_ROLLUP_LOCK_TTL_SECONDS):
        return {"skipped": "previous_run_in_progress"}
    try:
        with SessionLocal() as db:
            return {"rolled_up_days": archival_service.roll_up_queued_days(db)}
    finally:
        client.delete(_ROLLUP_LOCK_KEY)


@shared_task(
    name=CeleryTask.RUN_DAILY_ARCHIVAL,
    soft_time_limit=300,  # 5 min soft limit — raises SoftTimeLimitExceeded
    time_limit=360,  # 6 min hard limit — kills the worker
    acks_late=True,  # Re-queue if worker dies mid-task
    max_retries=3,
    default_retry_delay=60,
)
def run_daily_archival() -> dict:
    """Execute the daily rollup + retention job.

    The service internally limits batch size and wall time so this task
    is safe for first-run scenarios with millions of rows. If not all rows
    are processed, the next scheduled invocation continues automatically.
    """
    if not settings.data_lifecycle_enabled:
        return {"skipped": "data_lifecycle_disabled"}

    with SessionLocal() as db:
        try:
            summary = archival_service.run_daily_archival(db)
            logger.info("Daily archival completed: %s", summary)
            return summary
        except Exception:
            logger.exception("Daily archival task failed")
            raise
