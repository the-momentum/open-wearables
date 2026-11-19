from redis.exceptions import RedisError

from app.config import settings
from app.integrations.redis_client import get_redis_client
from app.utils.structured_logging import get_logger

logger = get_logger(__name__)

# One step, so parallel requests can't all pass before any is counted and the counter always expires.
_COUNT_ATTEMPT = """
local attempts = redis.call('INCR', KEYS[1])
if redis.call('TTL', KEYS[1]) < 0 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return {attempts, redis.call('TTL', KEYS[1])}
"""


def _key(email: str) -> str:
    return f"login_attempts:{email.strip().lower()}"


def count_attempt(email: str) -> int:
    """Count a login attempt before checking it; seconds until allowed again once over the limit, else 0."""
    try:
        attempts, ttl = get_redis_client().eval(_COUNT_ATTEMPT, 1, _key(email), settings.login_lockout_seconds)
    except RedisError as e:
        logger.warning("Login throttle unavailable, allowing the attempt", error=str(e))
        return 0
    return max(int(ttl), 1) if int(attempts) > settings.login_max_failed_attempts else 0


def clear(email: str) -> None:
    try:
        get_redis_client().delete(_key(email))
    except RedisError as e:
        logger.warning("Login throttle unavailable, attempts not cleared", error=str(e))
