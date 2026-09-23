"""Device type enum and priority configuration."""

from enum import StrEnum


class DeviceType(StrEnum):
    """Type of device that collected health data."""

    WATCH = "watch"
    BAND = "band"
    PHONE = "phone"
    SCALE = "scale"
    RING = "ring"
    OTHER = "other"
    UNKNOWN = "unknown"


# System-wide default device type priority (lower = higher priority)
# Used when user hasn't set custom priorities
DEFAULT_DEVICE_TYPE_PRIORITY: dict[DeviceType, int] = {
    DeviceType.WATCH: 1,
    DeviceType.BAND: 2,
    DeviceType.RING: 3,
    DeviceType.PHONE: 4,
    DeviceType.SCALE: 5,
    DeviceType.OTHER: 6,
    DeviceType.UNKNOWN: 99,
}
