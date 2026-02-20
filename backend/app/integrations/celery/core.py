import logging
import sys
from logging import Formatter, StreamHandler, getLogger

from app.config import settings
from celery import Celery, signals
from celery import current_app as current_celery_app


@signals.setup_logging.connect
def setup_celery_logging(**kwargs) -> None:
    """
    Configure Celery logging to use stdout instead of stderr.

    Some platforms convert stderr logs to level.error automatically, so we must use stdout
    to ensure platforms correctly identify log levels from JSON structured logs.

    This signal is called when Celery sets up its logging configuration.
    """
    # Get Celery's logger
    celery_logger = getLogger("celery")

    # Remove existing handlers that might use stderr
    celery_logger.handlers.clear()

    # Create a handler that uses stdout
    stdout_handler = StreamHandler(sys.stdout)
    stdout_handler.setFormatter(
        Formatter(
            "[%(asctime)s - %(name)s] (%(levelname)s) %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    # Add stdout handler to Celery logger
    celery_logger.addHandler(stdout_handler)
    celery_logger.setLevel(logging.INFO)
    celery_logger.propagate = False


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
            "samsung_sync": {},
        },
        task_routes={
            "app.integrations.celery.tasks.process_apple_upload_task.process_apple_upload": {"queue": "apple_sync"},
            "app.integrations.celery.tasks.process_samsung_upload_task.process_samsung_upload": {
                "queue": "samsung_sync"
            },
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
        "gc-stuck-garmin-backfills": {
            "task": "app.integrations.celery.tasks.garmin_gc_task.gc_stuck_backfills",
            "schedule": 180.0,  # Every 3 minutes
            "args": (),
            "kwargs": {},
        },
    }

    return celery_app
