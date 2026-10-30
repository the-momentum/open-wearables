"""Copies the history into the aggregate tables once per instance, a few minutes at a time."""

from logging import getLogger

from celery import shared_task
from sqlalchemy import Connection, event
from sqlalchemy.orm import Session, SessionTransaction

from app.constants.celery_tasks import CeleryTask
from app.database import SessionLocal
from app.integrations import redis_lock
from app.repositories.data_migration_repository import DataMigrationRepository
from app.services.aggregate_backfill_service import aggregate_backfill_service

logger = getLogger(__name__)

_LOCK_KEY = "aggregate_backfill:lock"
# Extended after every data source, so it only runs out on a holder that stopped making progress.
_LOCK_TTL_SECONDS = 420
# Work per run; the task then queues the next one, so no single run holds a worker for long.
_BUDGET_SECONDS = 240
# The default queue's thread pool ignores time limits; this is what stops a statement that would outlast the lock.
STATEMENT_TIMEOUT_SECONDS = 300
# Moves samples between data sources: a source it filled after the cursor went past would never be copied.
_AFTER_MIGRATION = "merge_duplicate_data_sources"


@shared_task(name=CeleryTask.RUN_AGGREGATE_BACKFILL, soft_time_limit=330, time_limit=360)
def run_aggregate_backfill() -> dict:
    """Run the backfill for a few minutes, then queue the next run until it is done. Started at startup and every
    15 minutes by beat, so a lost run picks up again; one run at a time."""
    token = redis_lock.acquire(_LOCK_KEY, _LOCK_TTL_SECONDS)
    if token is None:
        return {"skipped": "previous_run_in_progress"}
    try:
        with SessionLocal() as db:
            bound_statements(db)
            if aggregate_backfill_service.is_done(db):
                return {"skipped": "done"}
            if not DataMigrationRepository().is_completed(db, _AFTER_MIGRATION):
                return {"skipped": "waiting_for_data_source_merge"}
            done = aggregate_backfill_service.run(
                db, _BUDGET_SECONDS, keep_alive=lambda: redis_lock.extend(_LOCK_KEY, token, _LOCK_TTL_SECONDS)
            )
    finally:
        redis_lock.release(_LOCK_KEY, token)
    if not done:
        run_aggregate_backfill.apply_async(countdown=5)
    return {"done": done}


def bound_statements(db: Session) -> None:
    """Every transaction of the session cuts off a statement after STATEMENT_TIMEOUT_SECONDS."""

    @event.listens_for(db, "after_begin")
    def _set_timeout(_session: Session, _transaction: SessionTransaction, connection: Connection) -> None:
        connection.exec_driver_sql(f"SET LOCAL statement_timeout = {STATEMENT_TIMEOUT_SECONDS * 1000}")
