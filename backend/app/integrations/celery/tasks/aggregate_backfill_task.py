"""Copies the history into the aggregate tables once per instance, a few minutes at a time."""

from logging import getLogger

from celery import shared_task

from app.constants.celery_tasks import CeleryTask
from app.database import SessionLocal
from app.integrations.redis_client import get_redis_client
from app.services.aggregate_backfill_service import aggregate_backfill_service

logger = getLogger(__name__)

_LOCK_KEY = "aggregate_backfill:lock"
# Longer than the task may run, so a killed worker cannot hold the lock for good.
_LOCK_TTL_SECONDS = 420
# Work per run; the task then queues the next one, so no single run holds a worker for long.
_BUDGET_SECONDS = 240


@shared_task(name=CeleryTask.RUN_AGGREGATE_BACKFILL, soft_time_limit=330, time_limit=360)
def run_aggregate_backfill() -> dict:
    """Run the backfill for a few minutes, then queue the next run until it is done. Started at startup and every
    15 minutes by beat, so a lost run picks up again; one run at a time."""
    client = get_redis_client()
    if not client.set(_LOCK_KEY, "1", nx=True, ex=_LOCK_TTL_SECONDS):
        return {"skipped": "previous_run_in_progress"}
    try:
        with SessionLocal() as db:
            if aggregate_backfill_service.is_done(db):
                return {"skipped": "done"}
            done = aggregate_backfill_service.run(db, _BUDGET_SECONDS)
    finally:
        client.delete(_LOCK_KEY)
    if not done:
        run_aggregate_backfill.apply_async(countdown=5)
    return {"done": done}
