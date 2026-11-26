"""Days whose samples or events changed, waiting for the nightly rollup."""

from collections import defaultdict
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Any, cast
from uuid import UUID

from sqlalchemy import event as sa_event

from app.constants.celery_tasks import CeleryTask
from app.database import DbSession
from app.integrations import redis_lock
from app.integrations.redis_client import get_redis_client
from app.utils.structured_logging import get_logger

# A sorted set scored by the day, so a run takes the newest days first: after a provider sends years of
# history, the days clients look at are rolled up before the rest.
DIRTY_DAYS_KEY = "series_rollup:queue"
# Days a run has taken but not finished: a worker killed mid-run leaves them here, the next run puts them back.
IN_PROGRESS_KEY = "series_rollup:in_progress"

# Per source, its days queued or in progress, scored by the day: what a read asks to learn which of its days the
# rollup has not caught up with. The global queue is one set for every user, which a read could only range over.
SOURCE_DAYS_KEY = "series_rollup:source_days:{source_id}"
# The sources holding a SOURCE_DAYS_KEY, so dropping the queue can drop theirs too.
QUEUED_SOURCES_KEY = "series_rollup:queued_sources"

# Per source, the first local day an unfinished retention run has not deleted yet. Until the run finishes and
# archival_settings.deleted_before moves, this is what freezes the days already gone.
DELETED_BEFORE_KEY = "series_rollup:deleted_before"

# (user, local day) pairs to merge across the user's sources for source_selection=reconcile, scored by the day so
# a run takes the newest first. Filled by the rollup for recent days and by reads for the days they had to merge.
RECONCILE_DAYS_KEY = "series_reconcile:queue"

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

logger = get_logger(__name__)


# A day is finished for its source only once no write queued it again meanwhile: a write landing while the run
# rolled the day up has put it back on the global queue, and the source must keep it until the next run.
_FINISH = """
for i = 1, #ARGV do
    local member = ARGV[i]
    redis.call('SREM', KEYS[2], member)
    if not redis.call('ZSCORE', KEYS[1], member) then
        local split = string.find(member, ':', 1, true)
        local source_key = KEYS[3] .. string.sub(member, 1, split - 1)
        redis.call('ZREM', source_key, string.sub(member, split + 1))
        if redis.call('ZCARD', source_key) == 0 then
            redis.call('SREM', KEYS[4], string.sub(member, 1, split - 1))
        end
    end
end
"""
_SOURCE_DAYS_PREFIX = SOURCE_DAYS_KEY.removesuffix("{source_id}")

# Reading the queued sources and deleting their keys in one step, so a write in between leaves no orphan index.
_CLEAR = """
for _, source_id in ipairs(redis.call('SMEMBERS', KEYS[4])) do redis.call('DEL', KEYS[5] .. source_id) end
redis.call('DEL', KEYS[1], KEYS[2], KEYS[3], KEYS[4])
"""

# A read waits this long for the queue before it goes on with the rows as the rollup left them.
QUEUED_DAYS_TIMEOUT_SECONDS = 0.05
# Shared by every request of the process: each asks once and briefly, so a few threads never make a queue.
_queue_reads = ThreadPoolExecutor(max_workers=4, thread_name_prefix="rollup-queue-read")


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
            pipe = get_redis_client().pipeline()
            pipe.zadd(DIRTY_DAYS_KEY, _scored(members))
            _index_by_source(pipe, members)
            pipe.execute()
        except Exception as exc:
            # The day stays rolled up as it was; the next write to it, or the backfill, queues it again.
            logger.error("Failed to queue days for the rollup", exc_info=exc, days=len(members))


def pop_dirty_days(count: int) -> list[tuple[UUID, date]]:
    """Take up to ``count`` queued days off the queue; they stay in progress until finished or put back."""
    members = cast(list[str], get_redis_client().eval(_TAKE, 2, DIRTY_DAYS_KEY, IN_PROGRESS_KEY, count) or [])
    return [(UUID(source_id), date.fromisoformat(day)) for source_id, day in (m.split(":", 1) for m in members)]


def finish_dirty_days(days: Iterable[tuple[UUID, date]]) -> None:
    """The run is done with these days: rolled up, or dropped for good."""
    if members := _members(days):
        get_redis_client().eval(
            _FINISH, 4, DIRTY_DAYS_KEY, IN_PROGRESS_KEY, _SOURCE_DAYS_PREFIX, QUEUED_SOURCES_KEY, *members
        )


def requeue_dirty_days(days: Iterable[tuple[UUID, date]]) -> None:
    """Put days back that a run took but did not roll up."""
    if members := _members(days):
        pipe = get_redis_client().pipeline()
        pipe.zadd(DIRTY_DAYS_KEY, _scored(members))
        pipe.srem(IN_PROGRESS_KEY, *members)
        # Already indexed when queued; again so days queued before the index existed join it.
        _index_by_source(pipe, members)
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
    _index_by_source(pipe, members)
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
    get_redis_client().eval(
        _CLEAR, 5, DIRTY_DAYS_KEY, IN_PROGRESS_KEY, RECONCILE_DAYS_KEY, QUEUED_SOURCES_KEY, _SOURCE_DAYS_PREFIX
    )


def queue_reconcile_days(days: Iterable[tuple[UUID, date]]) -> None:
    """Queue (user, local day) pairs for the next rollup run to merge and store."""
    if members := _members(days):
        get_redis_client().zadd(RECONCILE_DAYS_KEY, _scored(members))


def pop_reconcile_days(count: int) -> list[tuple[UUID, date]]:
    """Take up to ``count`` queued (user, day) pairs, newest days first; what a run does not finish it queues
    again. A run killed in between loses them: a read merges such a day itself and queues it again."""
    members = cast(list[tuple[str, float]], get_redis_client().zpopmax(RECONCILE_DAYS_KEY, count))
    return [(UUID(user_id), date.fromisoformat(day)) for user_id, day in (m.split(":", 1) for m, _ in members)]


class QueuedDays:
    """The days of some sources the rollup has not caught up with: queued, or taken by a run not finished yet.
    Their day rows, if any, are older than their samples."""

    def __init__(self, days: dict[UUID, set[date]] | None = None, deleted_before: dict[UUID, date] | None = None):
        self.days = days or {}
        # Per source, the first day an unfinished retention run has not deleted: the days before it hold no samples.
        self.deleted_before = deleted_before or {}

    def of(self, source_id: UUID, frozen_before: date | None = None) -> set[date]:
        """The source's queued days that still hold their samples."""
        floor = max((day for day in (frozen_before, self.deleted_before.get(source_id)) if day), default=None)
        days = self.days.get(source_id, set())
        return {day for day in days if day >= floor} if floor else days

    def __bool__(self) -> bool:
        return any(self.days.values())


def queued_days(source_ids: Iterable[UUID], first_day: date, last_day: date) -> QueuedDays:
    """The sources' days from ``first_day`` to ``last_day`` the rollup has not caught up with: one round trip,
    a range of a small set per source, whatever the size of the queue."""
    source_ids = list(source_ids)
    if not source_ids:
        return QueuedDays()
    pipe = get_redis_client().pipeline(transaction=False)
    for source_id in source_ids:
        pipe.zrangebyscore(SOURCE_DAYS_KEY.format(source_id=source_id), first_day.toordinal(), last_day.toordinal())
    pipe.hmget(DELETED_BEFORE_KEY, [str(source_id) for source_id in source_ids])
    *ranges, deleted = pipe.execute()
    days = {
        source_id: {date.fromisoformat(day) for day in members}
        for source_id, members in zip(source_ids, ranges, strict=True)
        if members
    }
    deleted_before = {
        source_id: date.fromisoformat(day) for source_id, day in zip(source_ids, deleted, strict=True) if day
    }
    return QueuedDays(days, deleted_before)


def queued_days_soon(source_ids: Iterable[UUID], first_day: date, last_day: date) -> Callable[[], QueuedDays]:
    """Start :func:`queued_days` on a worker thread, so the caller's database query runs meanwhile; call the
    result for the answer. A queue that fails or is slow answers nothing queued: the rows stand as they are."""
    future = _queue_reads.submit(queued_days, list(source_ids), first_day, last_day)

    def result() -> QueuedDays:
        try:
            return future.result(timeout=QUEUED_DAYS_TIMEOUT_SECONDS)
        except Exception:
            # Expected under a slow Redis and harmless, so no Sentry event per read.
            future.cancel()
            logger.warning("Could not read the rollup queue; day rows are read as they are", exc_info=True)
            return QueuedDays()

    return result


def source_deleted_before(source_id: UUID) -> date | None:
    """The first local day of the source retention has not deleted yet, in a run that did not finish."""
    day = cast(str | None, get_redis_client().hget(DELETED_BEFORE_KEY, str(source_id)))
    return date.fromisoformat(day) if day else None


def mark_source_deleted_before(source_id: UUID, day: date) -> None:
    get_redis_client().hset(DELETED_BEFORE_KEY, str(source_id), day.isoformat())


def clear_sources_deleted_before() -> None:
    """A finished run moved archival_settings.deleted_before past every source's mark."""
    get_redis_client().delete(DELETED_BEFORE_KEY)


def _index_by_source(pipe: Any, members: Iterable[str]) -> None:
    by_source: dict[str, dict[str, int]] = defaultdict(dict)
    for member in members:
        source_id, day = member.rsplit(":", 1)
        by_source[source_id][day] = date.fromisoformat(day).toordinal()
    for source_id, days in by_source.items():
        pipe.zadd(SOURCE_DAYS_KEY.format(source_id=source_id), days)
    if by_source:
        pipe.sadd(QUEUED_SOURCES_KEY, *by_source)


def _members(days: Iterable[tuple[UUID, date]]) -> list[str]:
    return [f"{source_id}:{day.isoformat()}" for source_id, day in days]


def _scored(members: Iterable[str]) -> dict[str, int]:
    """Each "{source}:{day}" member scored by its day."""
    return {member: date.fromisoformat(member.rsplit(":", 1)[1]).toordinal() for member in members}
