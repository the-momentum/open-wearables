"""Flags the naps already stored for providers that don't report them, once per instance (#938)."""

import threading
import time
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
# Kept alive in the background while a run works, so it only runs out on a holder that died.
_LOCK_TTL_SECONDS = 420
# Work per run; the task then queues the next one, so no single run holds a worker for long.
_BUDGET_SECONDS = 240
_SOURCES_PER_QUERY = 100


# No time limit: a run stops between data sources on its own, and a limit hit inside a long source would count it as
# failed on every attempt, so the migration would never be recorded.
@shared_task(name=CeleryTask.CLASSIFY_SLEEP_NAPS, acks_late=True, reject_on_worker_lost=True)
def classify_sleep_naps(after: str | None = None, failed: int = 0) -> dict:
    """Flag the naps of the data sources after ``after`` for a few minutes, then queue the next run from there.

    Queued at startup until recorded as done. A failing data source is logged and skipped; the run is recorded only
    without failures, so the next startup tries again.
    """
    token = redis_lock.acquire(_LOCK_KEY, _LOCK_TTL_SECONDS)
    if token is None:
        return {"skipped": "previous_run_in_progress"}
    try:
        with redis_lock.kept_alive(_LOCK_KEY, token, _LOCK_TTL_SECONDS) as lost, SessionLocal() as db:
            bound_lock_waits(db)
            migrations = DataMigrationRepository()
            if migrations.is_completed(db, MIGRATION):
                return {"skipped": "done"}
            countdown = 5
            try:
                cursor, failed, finished = classify_sources(
                    db, UUID(after) if after else None, failed, _BUDGET_SECONDS, lost
                )
            except LockLostError as stopped:
                # Redis failed or another run took over: the continuation waits, then skips while another holds it.
                logger.warning("Sleep nap classification lost its lock, retrying later", data_source_id=after)
                cursor, failed, finished, countdown = stopped.after, stopped.failed, False, 60
            if finished and not failed:
                migrations.mark_completed(db, MIGRATION)
                db.commit()
    finally:
        redis_lock.release(_LOCK_KEY, token)
    if not finished:
        classify_sleep_naps.apply_async(
            kwargs={"after": str(cursor) if cursor else None, "failed": failed}, countdown=countdown
        )
    return {"finished": finished, "failed": failed}


def classify_sources(
    db: Session,
    after: UUID | None,
    failed: int,
    budget_seconds: float,
    lost: threading.Event | None = None,
) -> tuple[UUID | None, int, bool]:
    """Re-flag the data sources after ``after`` until the budget is spent; returns the last source done, the
    failures so far and whether every source is done. Commits per data source; raises LockLostError, with the
    current source rolled back, once ``lost`` is set."""
    deadline = time.monotonic() + budget_seconds
    sources = DataSourceRepository(DataSource)
    while batch := sources.sleep_sources(db, NAP_INFERRED_PROVIDERS, after, _SOURCES_PER_QUERY):
        for source_id, user_id in batch:
            if lost is not None and lost.is_set():
                raise LockLostError(after, failed)
            try:
                event_record_service.reclassify_sleep_naps(db, user_id, source_id, None)
            except Exception as exc:
                db.rollback()
                failed += 1
                logger.error("Failed to classify sleep naps", exc_info=exc, data_source_id=str(source_id))
            else:
                if lost is not None and lost.is_set():
                    db.rollback()
                    raise LockLostError(after, failed)
                db.commit()
            after = source_id
            if time.monotonic() >= deadline:
                return after, failed, False
    return after, failed, True


class LockLostError(Exception):
    """The run's Redis lock was lost, so another run may be classifying the same data sources."""

    def __init__(self, after: UUID | None, failed: int) -> None:
        super().__init__("lock lost")
        self.after, self.failed = after, failed


def bound_lock_waits(db: Session) -> None:
    """A live sync holding a lock fails the data source instead of stalling the run."""

    @event.listens_for(db, "after_begin")
    def _set_lock_timeout(_session: Session, _transaction: SessionTransaction, connection: Connection) -> None:
        connection.exec_driver_sql("SET LOCAL lock_timeout = '10s'")
