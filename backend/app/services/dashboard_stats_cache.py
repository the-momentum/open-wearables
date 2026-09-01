"""Redis-backed cache for the expensive dashboard total-data-points count.

A full ``COUNT(*)`` over ``data_point_series`` is a multi-second sequential scan, so the exact
figure is cached and served stale-while-revalidate:

* fresh cache hit -> return the exact cached value;
* stale cache hit -> return the (slightly old) exact value and trigger a background refresh;
* cold cache -> return the instant ``reltuples`` approximation and trigger a background refresh.

The exact recount runs in a Celery task (see ``refresh_dashboard_stats_task``), so no request ever
pays for the scan. A short-lived lock ensures only one refresh is in flight at a time.
"""

from logging import getLogger
from uuid import uuid4

import redis

from app.database import DbSession
from app.integrations.redis_client import get_redis_client
from app.services.timeseries_service import timeseries_service

logger = getLogger(__name__)

_CACHE_KEY = "dashboard:total_data_points"
_FRESH_KEY = "dashboard:total_data_points:fresh"
_LOCK_KEY = "dashboard:total_data_points:refreshing"

_FRESH_TTL_SECONDS = 300  # how long a cached value is considered fresh (no refresh triggered)
_LOCK_TTL_SECONDS = 120  # safety expiry so a crashed refresh cannot wedge the lock forever

# Compare-and-delete: only release the lock if we still own it (its value matches our token), so a
# slow or expired refresh can never delete a lock already acquired by a newer refresh cycle.
_RELEASE_IF_OWNER = "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end"


def get_total_data_points(db_session: DbSession) -> int:
    """Return the total data-point count, cheaply.

    Falls back to the approximate count if the cache is cold or Redis is unavailable, so the
    dashboard never blocks on the full scan.
    """
    try:
        client = get_redis_client()
        cached = client.get(_CACHE_KEY)
        if cached is not None:
            if not client.exists(_FRESH_KEY):
                _trigger_refresh(client)
            return int(cached)
        # Cold cache: approximate now, exact recount happens in the background.
        _trigger_refresh(client)
    except Exception:
        logger.warning("Dashboard total-data-points cache unavailable; using approximate count", exc_info=True)

    return timeseries_service.get_approximate_total_count(db_session)


def _trigger_refresh(client: redis.Redis) -> None:
    """Enqueue a background recount, at most one in flight at a time."""
    token = uuid4().hex
    if not client.set(_LOCK_KEY, token, nx=True, ex=_LOCK_TTL_SECONDS):
        return
    # Imported lazily to avoid a circular import (task -> this module -> task).
    from app.integrations.celery.tasks.refresh_dashboard_stats_task import refresh_dashboard_total_data_points

    # retry=False: never let broker connection retries block the dashboard request. The task
    # releases the lock (matching this token) when it finishes.
    try:
        refresh_dashboard_total_data_points.apply_async(args=[token], retry=False)
    except Exception:
        # Dispatch failed (e.g. broker down): free our lock so a later request can retry.
        logger.warning("Failed to dispatch dashboard stats refresh", exc_info=True)
        release_refresh_lock(token)


def store_total_data_points(count: int) -> None:
    """Persist a freshly computed exact count (called by the refresh task)."""
    client = get_redis_client()
    client.set(_CACHE_KEY, count)
    client.set(_FRESH_KEY, "1", ex=_FRESH_TTL_SECONDS)


def release_refresh_lock(token: str) -> None:
    """Release the refresh lock, but only if we still own it (its value matches ``token``)."""
    get_redis_client().eval(_RELEASE_IF_OWNER, 1, _LOCK_KEY, token)
