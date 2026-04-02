from app.config import settings
from celery import Celery
from celery import current_app as current_celery_app
from celery.schedules import crontab


def create_celery() -> Celery:
    celery_app: Celery = current_celery_app  # type: ignore[assignment]
    celery_app.conf.update(
        broker_url=settings.CELERY_BROKER_URL,
        result_backend=settings.CELERY_RESULT_BACKEND,
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="Europe/Warsaw",
        enable_utc=True,
        task_default_queue="agent-default",
        task_default_exchange="agent-default",
        result_expires=3 * 24 * 3600,
    )

    celery_app.autodiscover_tasks(["app.integrations.celery", "app.integrations.celery.tasks"])

    celery_app.conf.beat_schedule = {
        "dummy-task": {
            "task": "app.integrations.celery.tasks.dummy_task.dummy_task",
            "schedule": crontab(minute="*/1"),
        },
        "expire-sessions": {
            "task": "app.integrations.celery.tasks.expire_sessions.expire_sessions",
            "schedule": crontab(minute="*/5"),
        },
    }

    return celery_app
