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


def infer_device_type_from_model(device_model: str | None) -> DeviceType:
    """Infer device type from device model string.

    Handles Apple productType codes and common device model patterns.
    """
    if not device_model:
        return DeviceType.UNKNOWN

    model_lower = device_model.lower()

    # Apple productType codes
    if device_model.startswith("Watch"):
        return DeviceType.WATCH
    if device_model.startswith("iPhone"):
        return DeviceType.PHONE
    if device_model.startswith("iPad"):
        return DeviceType.PHONE  # Treat iPad as phone for priority purposes

    # Common keywords
    if "watch" in model_lower:
        return DeviceType.WATCH
    if "band" in model_lower or "vivosmart" in model_lower or "vivofit" in model_lower:
        return DeviceType.BAND
    if "ring" in model_lower or "oura" in model_lower:
        return DeviceType.RING
    if "phone" in model_lower:
        return DeviceType.PHONE
    if "scale" in model_lower or "index" in model_lower:
        return DeviceType.SCALE

    # Garmin device patterns
    if any(
        x in model_lower
        for x in ["forerunner", "fenix", "venu", "epix", "enduro", "instinct", "tactix", "approach"]
    ):
        return DeviceType.WATCH

    # Polar patterns
    if any(x in model_lower for x in ["vantage", "grit x", "pacer", "ignite", "unite"]):
        return DeviceType.WATCH

    # Suunto patterns
    if any(x in model_lower for x in ["suunto", "vertical", "race", "peak"]):
        return DeviceType.WATCH

    # Whoop patterns
    if "whoop" in model_lower:
        return DeviceType.BAND

    return DeviceType.OTHER


def infer_device_type_from_source_name(source_name: str | None) -> DeviceType:
    """Infer device type from original source name (for aggregated data).

    Used when device_model is not available (e.g., data from Zepp Life via Apple Health).
    """
    if not source_name:
        return DeviceType.UNKNOWN

    name_lower = source_name.lower()

    # Known aggregator apps
    if "autosleep" in name_lower:
        return DeviceType.WATCH  # AutoSleep requires Apple Watch
    if "mi band" in name_lower or "xiaomi" in name_lower:
        return DeviceType.BAND
    if "amazfit band" in name_lower:
        return DeviceType.BAND
    if "oura" in name_lower:
        return DeviceType.RING
    if "zepp life" in name_lower:
        return DeviceType.UNKNOWN  # Could be watch or band
    if "health" in name_lower and "apple" not in name_lower:
        return DeviceType.UNKNOWN  # Manual entry

    return DeviceType.UNKNOWN
