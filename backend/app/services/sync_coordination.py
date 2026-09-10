"""Shared sync coordination for linked OW accounts.

When multiple OpenWearables profiles share the same external provider
account (e.g. one Garmin account linked to N testers), only one profile
should make the API call or accept the inbound webhook.  All others are
*secondaries*: they receive a fan-out of the already-parsed data and a
LINKED_ACCOUNT sync status event that points at the primary.

Redis keys (scoped to provider + provider_user_id + scope):

  linked_sync:{provider}:{provider_user_id}:{scope}:primary
      String "{user_id}:{token}".  SET NX — first caller wins.

  linked_sync:{provider}:{provider_user_id}:{scope}:secondaries
      Redis SET of user_id strings — supports N-1 secondaries.

*scope* separates concurrent sync types, e.g. "pull" vs "backfill".
"""

import logging
import threading
from dataclasses import dataclass
from uuid import UUID, uuid4

from app.config import settings
from app.integrations.redis_client import get_redis_client
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)

_PREFIX = "linked_sync"

# Atomically delete a key only if its current value matches ARGV[1].
# Prevents releasing a lock that was already expired and re-acquired by
# another caller between our last GET and the DEL.
_RELEASE_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""

# Same guard as the release: only extend a lease we still own, never a successor's.
_RENEW_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("expire", KEYS[1], ARGV[2])
else
    return 0
end
"""


def _primary_key(provider: str, provider_user_id: str, scope: str) -> str:
    return f"{_PREFIX}:{provider}:{provider_user_id}:{scope}:primary"


def _ttl_for(scope: str) -> int:
    """Pull renews its lease as it works; the backfill scope spans tasks and cannot."""
    if scope == "pull":
        return settings.linked_sync_pull_lease_seconds
    return settings.linked_sync_backfill_lease_seconds


def _secondaries_key(provider: str, provider_user_id: str, scope: str) -> str:
    return f"{_PREFIX}:{provider}:{provider_user_id}:{scope}:secondaries"


def try_become_primary(
    provider: str,
    provider_user_id: str,
    user_id: UUID,
    *,
    scope: str = "pull",
) -> tuple[bool, str, UUID | None]:
    """Try to become the primary for a shared sync run.

    Returns ``(True, token, user_id)`` when the caller wins the lock.
    Returns ``(False, "", existing_primary_user_id)`` when another caller
    already holds it.  ``existing_primary_user_id`` is None when the key
    exists but cannot be parsed (treat as "lock held by unknown primary").

    The caller must keep the returned *token* and pass it to
    :func:`release_primary` when the sync run ends.
    """
    client = get_redis_client()
    key = _primary_key(provider, provider_user_id, scope)
    token = uuid4().hex
    value = f"{user_id}:{token}"

    acquired = bool(client.set(key, value, nx=True, ex=_ttl_for(scope)))
    if acquired:
        return True, token, user_id

    raw = client.get(key)
    if raw:
        raw_str = raw if isinstance(raw, str) else raw.decode()
        parts = raw_str.split(":", 1)
        try:
            return False, "", UUID(parts[0])
        except (ValueError, IndexError):
            pass
    return False, "", None


def release_primary(
    provider: str,
    provider_user_id: str,
    user_id: UUID,
    token: str,
    *,
    scope: str = "pull",
) -> bool:
    """Atomically release the primary lock if the token still matches.

    Returns True when the lock was deleted.
    """
    key = _primary_key(provider, provider_user_id, scope)
    value = f"{user_id}:{token}"
    return bool(get_redis_client().eval(_RELEASE_LUA, 1, key, value))


@dataclass
class _Lease:
    provider: str
    provider_user_id: str
    user_id: UUID
    token: str
    scope: str
    lost: bool = False


@dataclass
class _Renewer:
    """A bound lease plus the daemon thread holding it alive."""

    lease: _Lease
    stop: threading.Event
    thread: threading.Thread


# Bound per task thread; the renewer thread gets its _Lease by reference, since a
# thread-local is invisible from the thread it renews for.
_lease = threading.local()

# The renewer only ever waits on stop.set(), so a join this long means it is blocked
# in Redis; it is a daemon thread and dies with the worker either way.
_JOIN_TIMEOUT_SECONDS = 5.0


def renew_primary(
    provider: str,
    provider_user_id: str,
    user_id: UUID,
    token: str,
    *,
    scope: str = "pull",
) -> bool:
    """Extend the lease while the token still matches. False means we no longer hold it."""
    key = _primary_key(provider, provider_user_id, scope)
    value = f"{user_id}:{token}"
    return bool(get_redis_client().eval(_RENEW_LUA, 1, key, value, _ttl_for(scope)))


def bind_primary_lease(
    provider: str,
    provider_user_id: str | None,
    user_id: UUID,
    token: str,
    *,
    scope: str = "pull",
) -> None:
    """Hold a won lock alive from a daemon thread for as long as this run lasts.

    The thread dies with the worker process, so a killed or restarted worker stops
    renewing and the lock frees itself within one lease.  A no-op without a token, so
    callers that are not primary need no branch.
    """
    clear_primary_lease()
    if not token or not provider_user_id:
        return
    lease = _Lease(provider, provider_user_id, user_id, token, scope)
    stop = threading.Event()
    thread = threading.Thread(
        target=_renew_until_stopped,
        args=(lease, stop),
        name=f"lease-renew-{provider}-{scope}",
        daemon=True,
    )
    _lease.state = _Renewer(lease, stop, thread)
    thread.start()


def clear_primary_lease() -> None:
    """Stop renewing. Safe to call when nothing is bound, and safe to call twice."""
    state: _Renewer | None = getattr(_lease, "state", None)
    _lease.state = None
    if state is None:
        return
    state.stop.set()
    state.thread.join(timeout=_JOIN_TIMEOUT_SECONDS)


def reacquire_primary(
    provider: str,
    provider_user_id: str,
    user_id: UUID,
    token: str,
    *,
    scope: str = "pull",
) -> bool:
    """Retake a lapsed lease under the same token, only while nobody else holds the lock."""
    key = _primary_key(provider, provider_user_id, scope)
    value = f"{user_id}:{token}"
    return bool(get_redis_client().set(key, value, nx=True, ex=_ttl_for(scope)))


def _renew_until_stopped(lease: _Lease, stop: threading.Event) -> None:
    """Extend the lease every interval until the run ends or the lock is taken from us."""
    interval = settings.linked_sync_renew_interval_seconds
    while not stop.wait(interval):
        try:
            if renew_primary(lease.provider, lease.provider_user_id, lease.user_id, lease.token, scope=lease.scope):
                continue
            retaken = reacquire_primary(
                lease.provider, lease.provider_user_id, lease.user_id, lease.token, scope=lease.scope
            )
        except Exception as exc:
            # An unreachable Redis means nobody else can take the lock either, so keep holding.
            log_structured(
                logger,
                "warning",
                f"Could not renew {lease.provider} {lease.scope} lease: {exc}",
                provider=lease.provider,
                action="lease_renew_error",
                scope=lease.scope,
                user_id=str(lease.user_id),
            )
            continue
        if retaken:
            if stop.is_set():
                # The run ended while we were retaking it; don't leave a lock nobody will release.
                release_primary(lease.provider, lease.provider_user_id, lease.user_id, lease.token, scope=lease.scope)
                return
            log_structured(
                logger,
                "warning",
                f"Retook lapsed {lease.provider} {lease.scope} lease — it had expired unclaimed",
                provider=lease.provider,
                action="lease_retaken",
                scope=lease.scope,
                user_id=str(lease.user_id),
            )
            continue
        lease.lost = True
        log_structured(
            logger,
            "warning",
            f"Lost {lease.provider} {lease.scope} lease mid-sync — another profile now holds it",
            provider=lease.provider,
            action="lease_lost",
            scope=lease.scope,
            user_id=str(lease.user_id),
        )
        return


def lease_lost() -> bool:
    """True once a renewal found the lock reassigned: stop acting as primary."""
    state: _Renewer | None = getattr(_lease, "state", None)
    return state is not None and state.lease.lost


def store_primary_token(
    provider: str,
    provider_user_id: str,
    user_id: UUID,
    token: str,
    *,
    scope: str = "pull",
) -> None:
    """Persist the primary lock token so a different task can release it later.

    Necessary for long-running operations (e.g. Garmin backfill) that span
    multiple Celery tasks: the task that acquired the lock stores the token
    here; the completion task reads and deletes it via
    :func:`release_primary_for_user`.
    """
    key = f"{_PREFIX}:{provider}:{provider_user_id}:{scope}:token:{user_id}"
    get_redis_client().setex(key, _ttl_for(scope), token)


def release_primary_for_user(
    provider: str,
    provider_user_id: str,
    user_id: UUID,
    *,
    scope: str = "pull",
) -> bool:
    """Release the primary lock using the persisted token.

    Reads the token stored by :func:`store_primary_token`, deletes the token
    key, and atomically releases the primary lock.  Returns True when the lock
    was deleted.
    """
    token_key = f"{_PREFIX}:{provider}:{provider_user_id}:{scope}:token:{user_id}"
    client = get_redis_client()
    raw = client.get(token_key)
    if not raw:
        return False
    token = raw if isinstance(raw, str) else raw.decode()
    client.delete(token_key)
    return release_primary(provider, provider_user_id, user_id, token, scope=scope)


def register_secondary(
    provider: str,
    provider_user_id: str,
    user_id: UUID,
    *,
    scope: str = "pull",
) -> None:
    """Register *user_id* as a secondary for this shared sync run."""
    client = get_redis_client()
    key = _secondaries_key(provider, provider_user_id, scope)
    client.sadd(key, str(user_id))
    client.expire(key, _ttl_for(scope))


def get_secondary_user_ids(
    provider: str,
    provider_user_id: str,
    *,
    scope: str = "pull",
) -> list[UUID]:
    """Return all registered secondary user IDs for this shared sync run."""
    members = get_redis_client().smembers(_secondaries_key(provider, provider_user_id, scope))
    uids: list[UUID] = []
    for m in members:
        raw = m if isinstance(m, str) else m.decode()
        try:
            uids.append(UUID(raw))
        except ValueError:
            log_structured(
                logger,
                "warning",
                f"Ignoring invalid UUID in secondaries set: {raw}",
                provider=provider,
                action="invalid_secondary",
                scope=scope,
            )
    return uids


def clear_secondaries(
    provider: str,
    provider_user_id: str,
    *,
    scope: str = "pull",
) -> None:
    """Delete the secondaries set after fan-out is complete."""
    get_redis_client().delete(_secondaries_key(provider, provider_user_id, scope))


def release_stale_primary(
    provider: str,
    provider_user_id: str,
    *,
    scope: str = "pull",
) -> bool:
    """Unconditionally delete the primary lock.

    Use ONLY when the lock holder is confirmed gone (e.g. user deleted, connection
    revoked) so the lock would never be released naturally before TTL expiry.
    Returns True when the key was deleted.
    """
    return bool(get_redis_client().delete(_primary_key(provider, provider_user_id, scope)))
