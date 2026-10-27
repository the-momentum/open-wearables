"""Daily data lifecycle Celery task.

Runs once per day (via beat schedule) to:
1. Roll the days whose samples or events changed up into open_wearables day and session aggregates.
2. Delete samples older than delete_after_days, rolled up first.

Both are configured by the admin via archival_settings.
"""

from logging import getLogger

from celery import Task, shared_task

from app.config import settings
from app.constants.celery_tasks import CeleryTask
from app.database import SessionLocal
from app.integrations import rollup_queue
from app.integrations.redis_client import get_redis_client
from app.services.archival_service import archival_service
from app.utils.structured_logging import log_structured

logger = getLogger(__name__)

_ROLLUP_LOCK_KEY = "series_rollup:lock"
# Longer than either task may run, so a killed worker cannot hold the lock for good.
_ROLLUP_LOCK_TTL_SECONDS = 400


def _take_rollup_lock() -> bool:
    return bool(get_redis_client().set(_ROLLUP_LOCK_KEY, "1", nx=True, ex=_ROLLUP_LOCK_TTL_SECONDS))


def _release_rollup_lock() -> None:
    get_redis_client().delete(_ROLLUP_LOCK_KEY)


@shared_task(name=CeleryTask.ROLL_UP_QUEUED_DAYS, soft_time_limit=120, time_limit=150)
def roll_up_queued_days() -> dict:
    """Roll up the days whose samples or events changed, every 15 minutes and until none are left, never two runs
    at once.

    Runs whether or not the lifecycle tab is on: summaries and day reads are served from the rows it writes.
    """
    if not _take_rollup_lock():
        return {"skipped": "previous_run_in_progress"}
    try:
        with SessionLocal() as db:
            rolled_up = archival_service.roll_up_queued_days(db)
    finally:
        _release_rollup_lock()
    if rollup_queue.has_dirty_days():
        # Days left over start the next run right away, so a busy instance does not wait 15 minutes per minute of work.
        roll_up_queued_days.apply_async(countdown=1)
    return {"rolled_up_days": rolled_up}


@shared_task(
    name=CeleryTask.RUN_DAILY_ARCHIVAL,
    bind=True,
    soft_time_limit=300,  # 5 min soft limit — raises SoftTimeLimitExceeded
    time_limit=360,  # 6 min hard limit — kills the worker
    acks_late=True,  # Re-queue if worker dies mid-task
    max_retries=3,
    default_retry_delay=60,
)
def run_daily_archival(self: Task) -> dict:
    """Execute the daily rollup + retention job.

    The service internally limits batch size and wall time so this task
    is safe for first-run scenarios with millions of rows. If not all rows
    are processed, the next scheduled invocation continues automatically.
    """
    if not settings.data_lifecycle_enabled:
        return {"skipped": "data_lifecycle_disabled"}
    if not _take_rollup_lock():
        # The 15-minute run fires at 03:00 too; both roll up, so one waits for the other.
        raise self.retry(countdown=60)

    try:
        with SessionLocal() as db:
            summary = archival_service.run_daily_archival(db)
            log_structured(logger, "info", "Daily archival completed", **summary)
            return summary
    except Exception:
        # Raised on to Celery, whose integration reports it to Sentry.
        log_structured(logger, "error", "Daily archival task failed")
        raise
    finally:
        _release_rollup_lock()
