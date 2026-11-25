"""Repairs the HealthKit condensed series stored over their originals, once per instance (#1983)."""

import time
from collections import Counter
from collections.abc import Callable
from datetime import datetime, timezone
from typing import NamedTuple, get_args
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
from app.services.sdk.condensed_series import MIN_CONDENSED_AGE, Repair, repair_source
from app.utils.structured_logging import get_logger

logger = get_logger(__name__)

MIGRATION = "repair_condensed_series"
_LOCK_KEY = "repair_condensed_series:lock"
# Extended after every data source, so it only runs out on a holder that stopped making progress.
_LOCK_TTL_SECONDS = 1800
# Work per run; the task then queues the next one, so no single run holds a worker for long.
_BUDGET_SECONDS = 240
_SOURCES_PER_QUERY = 100


class RepairRun(NamedTuple):
    """The last data source a run did, its rows by action (and failed sources) and whether every source is done."""

    cursor: UUID | None
    done: Counter[str]
    finished: bool


@shared_task(name=CeleryTask.REPAIR_CONDENSED_SERIES)
def repair_condensed_series(after: str | None = None, failed: int = 0) -> dict:
    """Repair the data sources after ``after`` for a few minutes, then queue the next run from there.

    Queued at startup and every 15 minutes by beat until recorded as done, so a lost run picks up again; one run
    at a time. A failing data source is logged and skipped, and the run is then not recorded, so a later one
    goes over the sources again.
    """
    token = redis_lock.acquire(_LOCK_KEY, _LOCK_TTL_SECONDS)
    if token is None:
        return {"skipped": "previous_run_in_progress"}
    try:
        with SessionLocal() as db:
            bound_statements(db)
            migrations = DataMigrationRepository()
            if migrations.is_completed(db, MIGRATION):
                return {"skipped": "done"}
            run = repair_sources(
                db,
                UUID(after) if after else None,
                _BUDGET_SECONDS,
                keep_alive=lambda: redis_lock.extend(_LOCK_KEY, token, _LOCK_TTL_SECONDS),
            )
            failed += run.done["failed"]
            if run.finished and not failed:
                migrations.mark_completed(db, MIGRATION)
                db.commit()
    finally:
        redis_lock.release(_LOCK_KEY, token)
    if not run.finished:
        repair_condensed_series.apply_async(kwargs={"after": str(run.cursor), "failed": failed}, countdown=5)
    return {"finished": run.finished, "failed": failed, **{action: run.done[action] for action in get_args(Repair)}}


def repair_sources(
    db: Session,
    after: UUID | None,
    budget_seconds: float,
    keep_alive: Callable[[], bool] = lambda: True,
    now: datetime | None = None,
) -> RepairRun:
    """Repair the Apple data sources after ``after`` until the budget is spent or the lock is lost. Commits per
    data source; a failing one is rolled back, logged and counted under "failed"."""
    deadline = time.monotonic() + budget_seconds
    before = (now or datetime.now(timezone.utc)) - MIN_CONDENSED_AGE
    sources = DataSourceRepository(DataSource)
    done: Counter[str] = Counter()
    while batch := sources.apple_app_sources(db, after, _SOURCES_PER_QUERY):
        for source_id, user_id, app_id in batch:
            try:
                by_type = repair_source(db, source_id, user_id, app_id, before)
                db.commit()
                for (_, action), rows in by_type.items():
                    done[action] += rows
            except Exception as exc:
                db.rollback()
                done["failed"] += 1
                logger.error("Failed to repair condensed series", exc_info=exc, data_source_id=str(source_id))
            after = source_id
            if time.monotonic() >= deadline or not keep_alive():
                return RepairRun(after, done, False)
    return RepairRun(after, done, True)


def bound_statements(db: Session) -> None:
    """A live sync holding a lock fails the data source instead of stalling the run, and the planner's far too high
    cost estimates for the per-workout lookups don't JIT-compile every execution."""

    @event.listens_for(db, "after_begin")
    def _set_limits(_session: Session, _transaction: SessionTransaction, connection: Connection) -> None:
        connection.exec_driver_sql("SET LOCAL lock_timeout = '10s'")
        connection.exec_driver_sql("SET LOCAL jit = off")
