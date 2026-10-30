"""Days whose samples or events changed, waiting for the nightly rollup."""

from collections.abc import Iterable
from datetime import date
from logging import getLogger
from typing import cast
from uuid import UUID

from sqlalchemy import event as sa_event

from app.constants.celery_tasks import CeleryTask
from app.database import DbSession
from app.integrations import redis_lock
from app.integrations.redis_client import get_redis_client
from app.utils.sentry_helpers import log_and_capture_error

# A sorted set scored by the day, so a run takes the newest days first: after a provider sends years of
# history, the days clients look at are rolled up before the rest.
DIRTY_DAYS_KEY = "series_rollup:queue"
# Days a run has taken but not finished: a worker killed mid-run leaves them here, the next run puts them back.
IN_PROGRESS_KEY = "series_rollup:in_progress"

# Per source, the first local day an unfinished retention run has not deleted yet. Until the run finishes and
# archival_settings.deleted_before moves, this is what freezes the days already gone.
DELETED_BEFORE_KEY = "series_rollup:deleted_before"

# One rollup at a time, whoever runs it: two rolling up the same day would leave whichever read its samples first.
LOCK_KEY = "series_rollup:lock"
# Longer than any holder may run, so a killed worker cannot hold the lock for good.
_LOCK_TTL_SECONDS = 400

# ZPOPMAX and the hand-over to the in-progress set in one step, so a kill between the two cannot lose a day.
_TAKE = """
local popped = redis.call('ZPOPMAX', KEYS[1], ARGV[1])
local taken = {}
for i = 1, #popped, 2 do taken[#taken + 1] = popped[i] end
if #taken > 0 then redis.call('SADD', KEYS[2], unpack(taken)) end
return taken
"""

logger = getLogger(__name__)


def take_lock() -> str | None:
    """The token that releases the lock, or None while another rollup holds it."""
    return redis_lock.acquire(LOCK_KEY, _LOCK_TTL_SECONDS)


def release_lock(token: str) -> None:
    redis_lock.release(LOCK_KEY, token)


def mark_dirty_days(db_session: DbSession, days: Iterable[tuple[UUID, date]]) -> None:
    """Queue (data source, local day) pairs once the caller's transaction commits."""
    members = {f"{source_id}:{day.isoformat()}" for source_id, day in days}
    if not members:
        return

    @sa_event.listens_for(db_session, "after_commit", once=True)
    def _queue(_session: DbSession) -> None:
        try:
            get_redis_client().zadd(DIRTY_DAYS_KEY, _scored(members))
        except Exception as exc:
            # The day stays rolled up as it was; the next write to it, or the backfill, queues it again.
            log_and_capture_error(exc, logger, "Failed to queue days for the rollup", extra={"days": len(members)})


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
        pipe.zadd(DIRTY_DAYS_KEY, _scored(members))
        pipe.srem(IN_PROGRESS_KEY, *members)
        pipe.execute()


def recover_dirty_days() -> int:
    """Put back whatever a run that died left in progress; returns how many days."""
    client = get_redis_client()
    members = cast(set[str], client.smembers(IN_PROGRESS_KEY))
    if not members:
        return 0
    pipe = client.pipeline()
    pipe.zadd(DIRTY_DAYS_KEY, _scored(members))
    pipe.delete(IN_PROGRESS_KEY)
    pipe.execute()
    return len(members)


def has_dirty_days() -> bool:
    return bool(get_redis_client().zcard(DIRTY_DAYS_KEY))


def roll_up_soon() -> None:
    """Start a rollup now rather than at the next 15-minute run; one already going skips it."""
    from celery import current_app as celery_app  # noqa: PLC0415 - the task modules import this one

    try:
        celery_app.send_task(CeleryTask.ROLL_UP_QUEUED_DAYS, retry=False)
    except Exception:
        # The next 15-minute run rolls it up anyway.
        logger.warning("Could not start a rollup", exc_info=True)


def clear_dirty_days() -> None:
    """Drop the queue, while the rollup is off."""
    get_redis_client().delete(DIRTY_DAYS_KEY, IN_PROGRESS_KEY)


def source_deleted_before(source_id: UUID) -> date | None:
    """The first local day of the source retention has not deleted yet, in a run that did not finish."""
    day = cast(str | None, get_redis_client().hget(DELETED_BEFORE_KEY, str(source_id)))
    return date.fromisoformat(day) if day else None


def mark_source_deleted_before(source_id: UUID, day: date) -> None:
    get_redis_client().hset(DELETED_BEFORE_KEY, str(source_id), day.isoformat())


def clear_sources_deleted_before() -> None:
    """A finished run moved archival_settings.deleted_before past every source's mark."""
    get_redis_client().delete(DELETED_BEFORE_KEY)


def _members(days: Iterable[tuple[UUID, date]]) -> list[str]:
    return [f"{source_id}:{day.isoformat()}" for source_id, day in days]


def _scored(members: Iterable[str]) -> dict[str, int]:
    """Each "{source}:{day}" member scored by its day."""
    return {member: date.fromisoformat(member.rsplit(":", 1)[1]).toordinal() for member in members}
