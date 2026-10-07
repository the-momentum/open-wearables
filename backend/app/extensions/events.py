"""Core events an extension reacts to: the core queues the extension's Celery task with ``user_id``.

A user's events are coalesced, since a user with continuous webhooks completes a sync every few
minutes. The first event opens a window of ``extension_event_debounce_seconds`` and every event
inside it rides on the same task, which a beat sweep queues once the window has closed. An event
after that opens a new window, so delivery is at least once and nothing is dropped.
"""

import time
from collections.abc import Mapping

from celery import current_app
from redis import Redis
from redis.client import Pipeline

SYNC_COMPLETED = "sync.completed"
SUPPORTED_EVENTS = frozenset({SYNC_COMPLETED})

# Users taken off a pending set per round trip; also keeps the Lua unpack well under its stack limit.
_SWEEP_BATCH = 1000

_TAKE_DUE = """
local due = redis.call('ZRANGEBYSCORE', KEYS[1], '-inf', ARGV[1], 'LIMIT', 0, ARGV[2])
if #due > 0 then redis.call('ZREM', KEYS[1], unpack(due)) end
return due
"""

_handlers: dict[str, tuple[str, ...]] = {}


def pending_key(event: str) -> str:
    return f"ext:events:{event}:pending"


def register(handlers: Mapping[str, tuple[str, ...]]) -> None:
    """Set the task names queued per event, collected from the active extensions."""
    _handlers.clear()
    _handlers.update(handlers)


def subscribed(event: str) -> bool:
    return bool(_handlers.get(event))


def record(pipe: Pipeline, event: str, user_id: str) -> None:
    """Mark the user pending, keeping the time of their first event so the window does not slide."""
    pipe.zadd(pending_key(event), {user_id: time.time()}, nx=True)


def dispatch_due(client: Redis, debounce_seconds: float) -> int:
    """Queue every handler for the users whose window has closed; returns how many users were due."""
    take_due = client.register_script(_TAKE_DUE)
    cutoff = time.time() - debounce_seconds
    dispatched = 0
    for event, tasks in _handlers.items():
        while True:
            due: list[str] = take_due(keys=[pending_key(event)], args=[cutoff, _SWEEP_BATCH])
            for index, user_id in enumerate(due):
                try:
                    for task in tasks:
                        current_app.send_task(task, kwargs={"user_id": user_id})
                except Exception:
                    # Put back what was taken but not queued, due at once on the next sweep.
                    client.zadd(pending_key(event), dict.fromkeys(due[index:], 0), nx=True)
                    raise
            dispatched += len(due)
            if len(due) < _SWEEP_BATCH:
                break
    return dispatched
