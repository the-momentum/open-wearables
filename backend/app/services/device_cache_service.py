"""
Device cache service for frequently accessed device-related entities.

Uses Redis to cache device and device software lookups to avoid N+1 queries during data imports.
"""

from uuid import UUID

from app.config import settings
from app.integrations.redis_client import get_redis_client

redis_client = get_redis_client()


class DeviceCacheService:
    """Service for caching device-related entities in Redis."""

    @staticmethod
    def _device_key(provider_name: str, serial_number: str, name: str | None) -> str:
        """Generate Redis cache key for device."""
        name_part = name or "none"
        return f"device:{provider_name}:{serial_number}:{name_part}"

    @staticmethod
    def _device_software_key(device_id: UUID, version: str) -> str:
        """Generate Redis cache key for device software."""
        return f"device_software:{device_id}:{version}"

    def get_device_id(
        self,
        provider_name: str,
        serial_number: str,
        name: str | None = None,
    ) -> UUID | None:
        """Get cached device ID."""
        key = self._device_key(provider_name, serial_number, name)
        cached_id = redis_client.get(key)
        if cached_id:
            return UUID(cached_id)
        return None

    def cache_device(
        self,
        device_id: UUID,
        provider_name: str,
        serial_number: str,
        name: str | None = None,
    ) -> None:
        """Cache device ID with TTL from settings."""
        key = self._device_key(provider_name, serial_number, name)
        redis_client.setex(key, settings.device_cache_ttl_seconds, str(device_id))

    def get_device_software_id(self, device_id: UUID, version: str) -> UUID | None:
        """Get cached device software ID."""
        key = self._device_software_key(device_id, version)
        cached_id = redis_client.get(key)
        if cached_id:
            return UUID(cached_id)
        return None

    def cache_device_software(
        self,
        software_id: UUID,
        device_id: UUID,
        version: str,
    ) -> None:
        """Cache device software ID with TTL from settings."""
        key = self._device_software_key(device_id, version)
        redis_client.setex(key, settings.device_cache_ttl_seconds, str(software_id))

    def invalidate_device(
        self,
        provider_name: str,
        serial_number: str,
        name: str | None = None,
    ) -> None:
        """Invalidate cached device."""
        key = self._device_key(provider_name, serial_number, name)
        redis_client.delete(key)

    def invalidate_device_software(self, device_id: UUID, version: str) -> None:
        """Invalidate cached device software."""
        key = self._device_software_key(device_id, version)
        redis_client.delete(key)


# Singleton instance
device_cache_service = DeviceCacheService()
