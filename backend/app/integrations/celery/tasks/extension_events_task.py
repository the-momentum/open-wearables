from celery import shared_task

from app.config import settings
from app.constants.celery_tasks import CeleryTask
from app.extensions import events
from app.integrations.redis_client import get_redis_client


@shared_task(name=CeleryTask.DISPATCH_EXTENSION_EVENTS)
def dispatch_extension_events() -> dict:
    """Queue extension handlers for the users whose events have settled."""
    dispatched = events.dispatch_due(get_redis_client(), settings.extension_event_debounce_seconds)
    return {"dispatched_users": dispatched}
