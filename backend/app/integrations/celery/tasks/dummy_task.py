import logging

from celery import shared_task

log = logging.getLogger(__name__)


@shared_task(name="app.integrations.celery.tasks.dummy_task")
def dummy_task() -> None:
    log.info("Task performed")
