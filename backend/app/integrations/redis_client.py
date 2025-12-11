"""Centralized Redis client for the application."""

from functools import lru_cache

import redis

from app.config import settings


@lru_cache()
def get_redis_client() -> redis.Redis:
    """
    Get a singleton Redis client instance.

    Uses LRU cache to ensure only one Redis client instance is created
    and reused across the application.

    Returns:
        redis.Redis: Configured Redis client instance
    """
    return redis.from_url(
        settings.redis_url,
        decode_responses=True,
    )
