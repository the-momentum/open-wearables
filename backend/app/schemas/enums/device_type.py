"""Device type enum and priority configuration."""

from enum import StrEnum


class DeviceType(StrEnum):
    """Type of device that collected health data."""

    WATCH = "watch"
    BAND = "band"
    PHONE = "phone"
    SCALE = "scale"
    RING = "ring"
    TABLET = "tablet"
    CHEST_STRAP = "chest_strap"
    HR_SENSOR = "hr_sensor"
    HEADPHONES = "headphones"
    HEAD_MOUNTED = "head_mounted"
    GLASSES = "glasses"
    SMART_DISPLAY = "smart_display"
    BP_MONITOR = "bp_monitor"
    GLUCOSE_METER = "glucose_meter"
    THERMOMETER = "thermometer"
    SLEEP_MONITOR = "sleep_monitor"
    BIKE_COMPUTER = "bike_computer"
    FITNESS_MACHINE = "fitness_machine"
    OTHER = "other"
    UNKNOWN = "unknown"


# System-wide default device type priority (lower = higher priority)
# Used when user hasn't set custom priorities
DEFAULT_DEVICE_TYPE_PRIORITY: dict[DeviceType, int] = {
    DeviceType.WATCH: 1,
    DeviceType.BAND: 2,
    DeviceType.RING: 3,
    DeviceType.PHONE: 4,
    DeviceType.TABLET: 4,
    DeviceType.SCALE: 5,
    DeviceType.CHEST_STRAP: 6,
    DeviceType.HR_SENSOR: 6,
    DeviceType.HEADPHONES: 6,
    DeviceType.HEAD_MOUNTED: 6,
    DeviceType.GLASSES: 6,
    DeviceType.SMART_DISPLAY: 6,
    DeviceType.BP_MONITOR: 6,
    DeviceType.GLUCOSE_METER: 6,
    DeviceType.THERMOMETER: 6,
    DeviceType.SLEEP_MONITOR: 6,
    DeviceType.BIKE_COMPUTER: 6,
    DeviceType.FITNESS_MACHINE: 6,
    DeviceType.OTHER: 6,
    DeviceType.UNKNOWN: 99,
}
