import time
from logging import getLogger

from celery import Celery, signals
from celery import current_app as current_celery_app

from app.config import settings

logger = getLogger(__name__)

# Track task start times for duration metrics
_task_start_times: dict[str, float] = {}


@signals.setup_logging.connect
def setup_celery_logging(**kwargs) -> None:
    """Configure Celery to use the application's structured logging.

    This signal is called when Celery sets up its logging configuration.
    We delegate to the observability module for consistent log formatting.
    """
    from app.integrations.observability import configure_logging
    configure_logging()


@signals.celeryd_after_setup.connect
def init_worker_tracing(sender, instance, **kwargs) -> None:
    """Initialize OpenTelemetry tracing in Celery workers.

    Uses celeryd_after_setup signal which fires after worker setup,
    regardless of pool type (prefork, threads, etc.).
    """
    from app.integrations.observability.tracing import init_celery_tracing
    init_celery_tracing()


@signals.task_prerun.connect
def task_prerun_handler(task_id: str, task: object, **kwargs) -> None:
    """Record task start time for duration metrics."""
    _task_start_times[task_id] = time.time()

    if settings.otel_enabled:
        from app.integrations.observability import get_app_metrics
        metrics = get_app_metrics()
        if metrics:
            task_name = getattr(task, "name", "unknown")
            metrics.celery_tasks_started.add(1, {"task": task_name})


@signals.task_postrun.connect
def task_postrun_handler(task_id: str, task: object, retval: object, state: str, **kwargs) -> None:
    """Record task completion and duration metrics."""
    task_name = getattr(task, "name", "unknown")

    if task_id in _task_start_times:
        duration = time.time() - _task_start_times.pop(task_id)

        if settings.otel_enabled:
            from app.integrations.observability import get_app_metrics
            metrics = get_app_metrics()
            if metrics:
                metrics.celery_task_duration.record(duration, {"task": task_name})
                metrics.celery_tasks_completed.add(1, {"task": task_name, "state": state})


@signals.task_failure.connect
def task_failure_handler(task_id: str, task: object, exception: Exception, **kwargs) -> None:
    """Record task failures in metrics."""
    _task_start_times.pop(task_id, None)

    if settings.otel_enabled:
        from app.integrations.observability import get_app_metrics
        metrics = get_app_metrics()
        if metrics:
            task_name = getattr(task, "name", "unknown")
            error_type = type(exception).__name__
            metrics.celery_tasks_failed.add(1, {"task": task_name, "error_type": error_type})


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
