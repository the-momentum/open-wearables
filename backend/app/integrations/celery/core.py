import time
from logging import getLogger
from typing import Any

from app.config import settings
from app.integrations.observability import (
    configure_logging,
    record_task_completed,
    record_task_failed,
    record_task_started,
)
from app.integrations.observability.tracing import init_celery_tracing
from celery import Celery, signals
from celery import current_app as current_celery_app

logger = getLogger(__name__)

_task_start_times: dict[str, float] = {}


@signals.setup_logging.connect
def setup_celery_logging(**kwargs: Any) -> None:
    """Configure Celery to use the application's structured logging."""
    configure_logging()


@signals.celeryd_after_setup.connect
def init_worker_tracing(sender: Any, instance: Any, **kwargs: Any) -> None:
    """Initialize OpenTelemetry tracing in Celery workers."""
    init_celery_tracing()


@signals.task_prerun.connect
def task_prerun_handler(task_id: str, task: Any, **kwargs: Any) -> None:
    """Record task start time for duration metrics."""
    _task_start_times[task_id] = time.time()
    record_task_started(getattr(task, "name", "unknown"))


@signals.task_postrun.connect
def task_postrun_handler(task_id: str, task: Any, retval: Any, state: str, **kwargs: Any) -> None:
    """Record task completion and duration metrics."""
    if task_id in _task_start_times:
        duration = time.time() - _task_start_times.pop(task_id)
        record_task_completed(getattr(task, "name", "unknown"), state, duration)


@signals.task_failure.connect
def task_failure_handler(task_id: str, task: Any, exception: Exception, **kwargs: Any) -> None:
    """Record task failures in metrics."""
    _task_start_times.pop(task_id, None)
    record_task_failed(getattr(task, "name", "unknown"), type(exception).__name__)


def create_celery() -> Celery:
    celery_app: Celery = current_celery_app  # type: ignore[assignment]
    celery_app.conf.update(
        broker_url=settings.redis_url,
        result_backend=settings.redis_url,
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="Europe/Warsaw",
        enable_utc=True,
        task_default_queue="default",
        task_default_exchange="default",
        result_expires=3 * 24 * 3600,
        task_queues={
            "default": {},
            "apple_sync": {},
        },
        task_routes={
            "app.integrations.celery.tasks.process_apple_upload_task.process_apple_upload": {"queue": "apple_sync"},
        },
    )

    celery_app.autodiscover_tasks(["app.integrations.celery.tasks"])

    celery_app.conf.beat_schedule = {
        "sync-all-users-periodic": {
            "task": "app.integrations.celery.tasks.periodic_sync_task.sync_all_users",
            "schedule": float(settings.sync_interval_seconds),
            "args": (),  # No args - task calculates date range dynamically
            "kwargs": {"user_id": None},
        },
        "finalize-stale-sleeps-periodic": {
            "task": "app.integrations.celery.tasks.finalize_stale_sleep_task.finalize_stale_sleeps",
            "schedule": float(settings.sleep_sync_interval_seconds),
            "args": (),
            "kwargs": {},
        },
    }

    return celery_app
