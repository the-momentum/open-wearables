"""Per-client-IP request limits for public endpoints, counted in Redis."""

import time
from collections.abc import Callable

from fastapi import HTTPException, Request, status
from redis.exceptions import RedisError

from app.integrations.redis_client import get_redis_client
from app.utils.structured_logging import get_logger

logger = get_logger(__name__)


def rate_limit(scope: str, limit: Callable[[], int], window_seconds: int = 60) -> Callable[[Request], None]:
    """A dependency allowing `limit()` requests per client IP per fixed window.

    `limit` is read on every request so tests and settings changes take effect
    without a restart. When Redis is unavailable the request goes through:
    a limiter outage must not block onboarding.
    """

    def dependency(request: Request) -> None:
        client_ip = request.client.host if request.client else "unknown"
        window = int(time.time()) // window_seconds
        key = f"rate_limit:{scope}:{client_ip}:{window}"
        try:
            redis = get_redis_client()
            count = redis.incr(key)
            if count == 1:
                redis.expire(key, window_seconds)
        except RedisError as exc:
            logger.warning("Rate limiter unavailable", scope=scope, error=str(exc))
            return

        if count > limit():
            retry_after = window_seconds - int(time.time()) % window_seconds
            logger.warning("Rate limit exceeded", scope=scope, client_ip=client_ip)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many attempts. Try again in a minute.",
                headers={"Retry-After": str(retry_after)},
            )

    return dependency
