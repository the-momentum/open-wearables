"""Redis locks held by a token, so a holder whose lock expired can neither release nor extend one taken since."""

import threading
from collections.abc import Generator
from contextlib import contextmanager
from uuid import uuid4

from app.integrations.redis_client import get_redis_client

_RELEASE_IF_OWNER = "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end"
_EXTEND_IF_OWNER = (
    "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('expire', KEYS[1], ARGV[2]) else return 0 end"
)


def acquire(key: str, ttl_seconds: int) -> str | None:
    """The token that holds the lock, or None when someone else does."""
    token = uuid4().hex
    return token if get_redis_client().set(key, token, nx=True, ex=ttl_seconds) else None


def extend(key: str, token: str, ttl_seconds: int) -> bool:
    """Push the expiry out again; False once the lock is no longer the token's."""
    return bool(get_redis_client().eval(_EXTEND_IF_OWNER, 1, key, token, ttl_seconds))


def release(key: str, token: str) -> None:
    get_redis_client().eval(_RELEASE_IF_OWNER, 1, key, token)


@contextmanager
def kept_alive(key: str, token: str, ttl_seconds: int) -> Generator[None]:
    """Extend the lock in the background every third of its TTL while the block runs, however long one step takes."""
    stop = threading.Event()

    def renew() -> None:
        while not stop.wait(ttl_seconds / 3):
            if not extend(key, token, ttl_seconds):
                return

    thread = threading.Thread(target=renew, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join()
