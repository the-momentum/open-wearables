"""Core backfill state: Redis key helper, trace IDs, lock."""

import logging
from uuid import UUID, uuid4

from app.integrations.redis_client import get_redis_client
from app.services.providers.garmin.backfill_config import (
    BACKFILL_LOCK_TTL,
    REDIS_PREFIX,
    REDIS_TTL,
)

logger = logging.getLogger(__name__)


def _get_key(user_id: str | UUID, *parts: str) -> str:
    """Generate a namespaced Redis key for backfill tracking."""
    return ":".join([REDIS_PREFIX, str(user_id), *parts])


# ---------------------------------------------------------------------------
# Trace IDs
# ---------------------------------------------------------------------------


def set_trace_id(user_id: str | UUID) -> str:
    """Generate and store a session-level trace ID for a user's backfill."""
    trace_id = str(uuid4())[:8]
    get_redis_client().setex(_get_key(user_id, "trace_id"), REDIS_TTL, trace_id)
    return trace_id


def get_trace_id(user_id: str | UUID, data_type: str | None = None) -> str | None:
    """Return the active backfill trace ID for a user, optionally per-type."""
    if data_type:
        return get_redis_client().get(_get_key(user_id, "types", data_type, "trace_id"))  # ty:ignore[invalid-return-type]
    return get_redis_client().get(_get_key(user_id, "trace_id"))  # ty:ignore[invalid-return-type]


def set_type_trace_id(user_id: str | UUID, data_type: str) -> str:
    """Generate and store a per-type trace ID for a specific backfill data type."""
    trace_id = str(uuid4())[:8]
    get_redis_client().setex(_get_key(user_id, "types", data_type, "trace_id"), REDIS_TTL, trace_id)
    return trace_id


# ---------------------------------------------------------------------------
# Lock
# ---------------------------------------------------------------------------


def acquire_backfill_lock(user_id: str | UUID) -> str | None:
    """Try to acquire exclusive backfill lock.

    Returns a unique token string on success, or None if already locked.
    The token is also persisted in Redis so cross-task release is possible.
    """
    uid = str(user_id)
    token = uuid4().hex
    lock_key = _get_key(uid, "lock")
    acquired = bool(get_redis_client().set(lock_key, token, nx=True, ex=BACKFILL_LOCK_TTL))
    if acquired:
        get_redis_client().setex(_get_key(uid, "lock_token"), BACKFILL_LOCK_TTL, token)
    return token if acquired else None


_RELEASE_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""


def release_backfill_lock(user_id: str | UUID, token: str | None = None) -> bool:
    """Atomically release the backfill lock if it still belongs to the caller.

    If *token* is omitted the stored companion key is used (enables cross-task
    release where the original token was not threaded through).  Returns True
    when the lock was actually deleted.
    """
    uid = str(user_id)
    lock_key = _get_key(uid, "lock")
    token_key = _get_key(uid, "lock_token")
    if token is None:
        token = get_redis_client().get(token_key)  # ty:ignore[invalid-assignment]
    if not token:
        return False
    result = bool(get_redis_client().eval(_RELEASE_LUA, 1, lock_key, token))
    get_redis_client().delete(token_key)
    return result


def force_release_backfill_lock(user_id: str | UUID) -> None:
    """Unconditionally release the backfill lock — use only from admin paths (e.g. user deletion)."""
    uid = str(user_id)
    get_redis_client().delete(_get_key(uid, "lock"), _get_key(uid, "lock_token"))
