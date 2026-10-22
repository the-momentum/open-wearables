"""Days whose samples or events changed, waiting for the nightly rollup."""

from collections.abc import Iterable
from datetime import date
from logging import getLogger
from typing import cast
from uuid import UUID

from sqlalchemy import event as sa_event

from app.database import DbSession
from app.integrations.redis_client import get_redis_client

DIRTY_DAYS_KEY = "series_rollup:dirty_days"

logger = getLogger(__name__)


def mark_dirty_days(db_session: DbSession, days: Iterable[tuple[UUID, date]]) -> None:
    """Queue (data source, local day) pairs once the caller's transaction commits."""
    members = {f"{source_id}:{day.isoformat()}" for source_id, day in days}
    if not members:
        return

    @sa_event.listens_for(db_session, "after_commit", once=True)
    def _queue(_session: DbSession) -> None:
        try:
            get_redis_client().sadd(DIRTY_DAYS_KEY, *members)
        except Exception:
            # The day stays rolled up as it was; the next write to it, or the backfill, queues it again.
            logger.warning("Failed to queue %d days for the rollup", len(members), exc_info=True)


def pop_dirty_days(count: int) -> list[tuple[UUID, date]]:
    """Take up to ``count`` queued days off the queue."""
    members = cast(list[str], get_redis_client().spop(DIRTY_DAYS_KEY, count) or [])
    return [(UUID(source_id), date.fromisoformat(day)) for source_id, day in (m.split(":", 1) for m in members)]


def requeue_dirty_days(days: Iterable[tuple[UUID, date]]) -> None:
    """Put days back that a run took but did not roll up."""
    if members := [f"{source_id}:{day.isoformat()}" for source_id, day in days]:
        get_redis_client().sadd(DIRTY_DAYS_KEY, *members)


def clear_dirty_days() -> None:
    """Drop the queue, while the rollup is off."""
    get_redis_client().delete(DIRTY_DAYS_KEY)
