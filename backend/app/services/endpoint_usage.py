"""Per-endpoint request counters for the anonymous usage telemetry ping.

Requests are counted by route template, caller type and status class. Raw paths,
query strings, IDs and user agents never enter a counter - see
docs/dev-guides/telemetry.mdx for the full reference.

Counters are buffered in process memory and flushed to a per-day Redis hash, so
recording a request costs a dict increment and the API never waits on Redis.
"""

import threading
import time
from collections import Counter
from datetime import date, datetime, timezone
from logging import getLogger
from typing import Any, cast

from fastapi.routing import APIRoute
from jose import JWTError, jwt
from starlette.types import Scope

from app.config import settings
from app.integrations.redis_client import get_redis_client
from app.schemas.enums import ProviderName

logger = getLogger(__name__)

UNMATCHED = "unmatched"
UNRESOLVED = "unresolved"

_COUNTED_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE"})
# Routes whose mere usage says something sensitive about an instance's users. The
# payload's `menstrual_tracking_used` flag already covers the product question.
_EXCLUDED_ROUTE_MARKERS = ("/menstrual-cycles",)
# `{provider}` is the one path parameter worth keeping: a closed enum, not an ID.
_PROVIDERS = frozenset(provider.value for provider in ProviderName)

_REDIS_KEY_PREFIX = "telemetry:endpoint_usage:"
_REDIS_TTL_SECONDS = 3 * 24 * 3600
_FIELD_SEPARATOR = "|"

_BUCKETS = (
    (10, "1-10"),
    (100, "11-100"),
    (1_000, "101-1k"),
    (10_000, "1k-10k"),
    (100_000, "10k-100k"),
    (1_000_000, "100k-1M"),
)


def usage_bucket(count: int) -> str:
    """Coarse order-of-magnitude label, so exact volumes never leave the instance."""
    for upper, label in _BUCKETS:
        if count <= upper:
            return label
    return "1M+"


def route_key(scope: Scope, status_code: int) -> str | None:
    """The counter key for a request, or None when the request is not counted."""
    method = scope["method"]
    if method not in _COUNTED_METHODS:
        return None

    route = scope.get("route")
    if route is None:
        # Docs and static files carry no route either, so only a real 404 counts here.
        return UNMATCHED if status_code == 404 else None
    if not isinstance(route, APIRoute):
        return None

    template = _path_template(scope["path"], scope.get("path_params", {}))
    if any(marker in template for marker in _EXCLUDED_ROUTE_MARKERS):
        return None
    return f"{method} {template}"


def _path_template(path: str, path_params: dict[str, Any]) -> str:
    """Rebuild the route template by swapping path parameter values for their names.

    `route.path` would be simpler, but for nested routers it only holds the innermost
    part ("/stats" for "/api/v1/dashboard/stats"). Working from the matched parameters
    needs no framework internals, and a value that cannot be placed fails closed.
    """
    names_by_value = {
        str(value): name for name, value in path_params.items() if not (name == "provider" and value in _PROVIDERS)
    }
    segments = path.split("/")
    if not names_by_value.keys() <= set(segments):
        # A parameter that is not a whole path segment: never emit the raw path.
        return UNRESOLVED
    return "/".join(f"{{{names_by_value[segment]}}}" if segment in names_by_value else segment for segment in segments)


def caller_type(authorization: str | None, api_key: str | None) -> str:
    """Which credential the request presented: developer_jwt, sdk_token, api_key or none.

    Mirrors the precedence of the auth dependencies (JWT first, then API key). Expiry
    is ignored - the status class already tells whether the call was accepted.
    """
    if authorization and authorization[:7].lower() == "bearer ":
        try:
            claims = jwt.decode(
                authorization[7:],
                settings.secret_key,
                algorithms=[settings.algorithm],
                options={"verify_exp": False, "verify_aud": False},
            )
        except JWTError:
            claims = None
        if claims is not None:
            return "sdk_token" if claims.get("scope") == "sdk" else "developer_jwt"
    if api_key:
        return "api_key"
    return "none"


class EndpointUsageRecorder:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._buffer: Counter[tuple[date, str]] = Counter()
        self._last_flush = time.monotonic()

    def record(self, key: str, auth: str, status_code: int) -> None:
        field = _FIELD_SEPARATOR.join((auth, f"{status_code // 100}xx", key))
        # The day is fixed here, not at flush time, so a flush just after midnight
        # still lands in the right bucket.
        day = datetime.now(timezone.utc).date()
        with self._lock:
            self._buffer[(day, field)] += 1

    def claim_flush(self) -> bool:
        """True at most once per flush interval - the caller then owns the flush."""
        now = time.monotonic()
        with self._lock:
            if now - self._last_flush < settings.telemetry_usage_flush_interval_seconds:
                return False
            self._last_flush = now
            return True

    def flush(self) -> None:
        with self._lock:
            pending, self._buffer = self._buffer, Counter()
        if not pending:
            return
        try:
            pipeline = get_redis_client().pipeline(transaction=False)
            for (day, field), count in pending.items():
                pipeline.hincrby(_redis_key(day), field, count)
            for day in {day for day, _ in pending}:
                pipeline.expire(_redis_key(day), _REDIS_TTL_SECONDS)
            pipeline.execute()
        except Exception:
            # Best effort: a lost flush interval is not worth retrying or surfacing.
            logger.debug("Could not flush endpoint usage counters", exc_info=True)

    def read_day(self, day: date) -> dict[str, dict[str, dict[str, str]]]:
        """Bucketed counters for one UTC day as {route: {auth: {status_class: bucket}}}."""
        routes: dict[str, dict[str, dict[str, str]]] = {}
        # decode_responses=True on the shared client: fields and values are str
        counters = cast(dict[str, str], get_redis_client().hgetall(_redis_key(day)))
        for field, count in counters.items():
            auth, status_class, key = field.split(_FIELD_SEPARATOR, 2)
            routes.setdefault(key, {}).setdefault(auth, {})[status_class] = usage_bucket(int(count))
        return routes


def _redis_key(day: date) -> str:
    return f"{_REDIS_KEY_PREFIX}{day.isoformat()}"


endpoint_usage = EndpointUsageRecorder()
