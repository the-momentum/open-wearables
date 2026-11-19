from redis.exceptions import RedisError

from app.config import settings
from app.integrations.redis_client import get_redis_client
from app.utils.structured_logging import get_logger

logger = get_logger(__name__)


def _key(email: str) -> str:
    return f"login_failures:{email.strip().lower()}"


def seconds_until_allowed(email: str) -> int:
    """Seconds left of the lockout once an email ran out of failed attempts, else 0."""
    try:
        redis = get_redis_client()
        failures = redis.get(_key(email))
        if failures is None or int(failures) < settings.login_max_failed_attempts:
            return 0
        return max(int(redis.ttl(_key(email))), 1)
    except RedisError as e:
        logger.warning("Login throttle unavailable, allowing the attempt", error=str(e))
        return 0


def record_failure(email: str) -> None:
    """The window starts at the first failure, so the lockout ends at a fixed time."""
    try:
        redis = get_redis_client()
        if redis.incr(_key(email)) == 1:
            redis.expire(_key(email), settings.login_lockout_seconds)
    except RedisError as e:
        logger.warning("Login throttle unavailable, failure not counted", error=str(e))


def clear(email: str) -> None:
    try:
        get_redis_client().delete(_key(email))
    except RedisError as e:
        logger.warning("Login throttle unavailable, failures not cleared", error=str(e))
