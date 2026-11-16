"""Flags the naps already stored for providers that don't report them, once per instance (#938)."""

import time
from collections.abc import Callable
from uuid import UUID

from celery import shared_task
from sqlalchemy import Connection, event
from sqlalchemy.orm import Session, SessionTransaction

from app.constants.celery_tasks import CeleryTask
from app.database import SessionLocal
from app.integrations import redis_lock
from app.models import DataSource
from app.repositories.data_migration_repository import DataMigrationRepository
from app.repositories.data_source_repository import DataSourceRepository
from app.services.event_record_service import event_record_service
from app.services.sleep_naps import NAP_INFERRED_PROVIDERS
from app.utils.structured_logging import get_logger

logger = get_logger(__name__)

MIGRATION = "classify_sleep_naps"
_LOCK_KEY = "classify_sleep_naps:lock"
# Extended after every data source, so it only runs out on a holder that stopped making progress.
_LOCK_TTL_SECONDS = 1800
# Work per run; the task then queues the next one, so no single run holds a worker for long.
_BUDGET_SECONDS = 240
_SOURCES_PER_QUERY = 100


@shared_task(name=CeleryTask.CLASSIFY_SLEEP_NAPS)
def classify_sleep_naps(after: str | None = None, failed: int = 0) -> dict:
    """Flag the naps of the data sources after ``after`` for a few minutes, then queue the next run from there.

    Queued at startup and every 15 minutes by beat until recorded as done, so a lost run picks up again; one run
    at a time. A failing data source is logged and skipped, and the run is then not recorded, so a later one
    goes over the sources again.
    """
    token = redis_lock.acquire(_LOCK_KEY, _LOCK_TTL_SECONDS)
    if token is None:
        return {"skipped": "previous_run_in_progress"}
    try:
        with SessionLocal() as db:
            bound_lock_waits(db)
            migrations = DataMigrationRepository()
            if migrations.is_completed(db, MIGRATION):
                return {"skipped": "done"}
            cursor, failed, finished = classify_sources(
                db,
                UUID(after) if after else None,
                failed,
                _BUDGET_SECONDS,
                keep_alive=lambda: redis_lock.extend(_LOCK_KEY, token, _LOCK_TTL_SECONDS),
            )
            if finished and not failed:
                migrations.mark_completed(db, MIGRATION)
                db.commit()
    finally:
        redis_lock.release(_LOCK_KEY, token)
    if not finished:
        classify_sleep_naps.apply_async(kwargs={"after": str(cursor), "failed": failed}, countdown=5)
    return {"finished": finished, "failed": failed}


def classify_sources(
    db: Session,
    after: UUID | None,
    failed: int,
    budget_seconds: float,
    keep_alive: Callable[[], bool] = lambda: True,
) -> tuple[UUID | None, int, bool]:
    """Re-flag the data sources after ``after`` until the budget is spent or the lock is lost; returns the last
    source done, the failures so far and whether every source is done. Commits per data source."""
    deadline = time.monotonic() + budget_seconds
    sources = DataSourceRepository(DataSource)
    while batch := sources.sleep_sources(db, NAP_INFERRED_PROVIDERS, after, _SOURCES_PER_QUERY):
        for source_id, user_id in batch:
            try:
                event_record_service.reclassify_sleep_naps(db, user_id, source_id, None)
                db.commit()
            except Exception as exc:
                db.rollback()
                failed += 1
                logger.error("Failed to classify sleep naps", exc_info=exc, data_source_id=str(source_id))
            after = source_id
            if time.monotonic() >= deadline or not keep_alive():
                return after, failed, False
    return after, failed, True


def bound_lock_waits(db: Session) -> None:
    """A live sync holding a lock fails the data source instead of stalling the run."""

    @event.listens_for(db, "after_begin")
    def _set_lock_timeout(_session: Session, _transaction: SessionTransaction, connection: Connection) -> None:
        connection.exec_driver_sql("SET LOCAL lock_timeout = '10s'")
