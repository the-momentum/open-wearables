from app.config import settings
from celery import Celery
from celery import current_app as current_celery_app


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
            "schedule": float(settings.sleep_interval_seconds),
            "args": (),
            "kwargs": {},
        },
    }

    return celery_app
