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
# Days a run has taken but not finished: a worker killed mid-run leaves them here, the next run puts them back.
IN_PROGRESS_KEY = "series_rollup:in_progress"

# SPOP and the hand-over to the in-progress set in one step, so a kill between the two cannot lose a day.
_TAKE = """
local taken = redis.call('SPOP', KEYS[1], ARGV[1])
if #taken > 0 then redis.call('SADD', KEYS[2], unpack(taken)) end
return taken
"""

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
    """Take up to ``count`` queued days off the queue; they stay in progress until finished or put back."""
    members = cast(list[str], get_redis_client().eval(_TAKE, 2, DIRTY_DAYS_KEY, IN_PROGRESS_KEY, count) or [])
    return [(UUID(source_id), date.fromisoformat(day)) for source_id, day in (m.split(":", 1) for m in members)]


def finish_dirty_days(days: Iterable[tuple[UUID, date]]) -> None:
    """The run is done with these days: rolled up, or dropped for good."""
    if members := _members(days):
        get_redis_client().srem(IN_PROGRESS_KEY, *members)


def requeue_dirty_days(days: Iterable[tuple[UUID, date]]) -> None:
    """Put days back that a run took but did not roll up."""
    if members := _members(days):
        pipe = get_redis_client().pipeline()
        pipe.sadd(DIRTY_DAYS_KEY, *members)
        pipe.srem(IN_PROGRESS_KEY, *members)
        pipe.execute()


def recover_dirty_days() -> int:
    """Put back whatever a run that died left in progress; returns how many days."""
    client = get_redis_client()
    members = cast(set[str], client.smembers(IN_PROGRESS_KEY))
    if not members:
        return 0
    pipe = client.pipeline()
    pipe.sadd(DIRTY_DAYS_KEY, *members)
    pipe.delete(IN_PROGRESS_KEY)
    pipe.execute()
    return len(members)


def clear_dirty_days() -> None:
    """Drop the queue, while the rollup is off."""
    get_redis_client().delete(DIRTY_DAYS_KEY, IN_PROGRESS_KEY)


def _members(days: Iterable[tuple[UUID, date]]) -> list[str]:
    return [f"{source_id}:{day.isoformat()}" for source_id, day in days]
