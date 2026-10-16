"""Device resolution utilities for mobile SDK data (HealthKit, Health Connect, Samsung Health)."""

from app.constants.devices_map import is_apple_own_source, is_host_model, map_reported_device_type
from app.schemas.enums import DeviceType
from app.schemas.providers.mobile_sdk import OSVersion, SourceInfo


def _format_os_version(os_version: OSVersion | None) -> str | None:
    if not os_version:
        return None
    return f"{os_version.major_version}.{os_version.minor_version}.{os_version.patch_version}"


def _get_source_app_id(source: SourceInfo) -> str | None:
    return source.app_id or source.bundle_identifier


def _get_device_model(source: SourceInfo | None) -> str | None:
    if not source:
        return None
    app_id = _get_source_app_id(source)
    # Apple's own sources tag some Watch samples with the paired iPhone's model; hardware is the producer
    if source.device_hardware_version and is_apple_own_source(app_id):
        return source.device_hardware_version
    model = source.device_model or source.product_type or None
    # iOS SDKs before the fix for third-party writes report the relaying iPhone as the writer's model
    return None if is_host_model(app_id, model) else model


def _get_original_source_name(source: SourceInfo | None) -> str | None:
    if not source:
        return None
    if source.name:
        return source.name
    if source.device_name:
        return source.device_name
    # Third-party Health Connect writers (Peloton, Strava, Zwift, etc.)
    # never set ``name`` or ``device_name`` — they only populate the
    # writer's package identifier via ``appId`` (HC SDK ``DataOrigin``)
    # or ``bundleIdentifier`` (HealthKit Source bundle id). Falling back
    # to those keeps the workout's original provenance instead of
    # collapsing it to "unknown".
    return _get_source_app_id(source)


def extract_device_info(source: SourceInfo | None) -> tuple[str | None, str | None, str | None]:
    """Extract device information from SourceInfo.

    Returns:
        Tuple of (device_model, software_version, original_source_name).
    """
    if not source:
        return None, None, None

    device_model = _get_device_model(source)
    software_version = _format_os_version(source.operating_system_version)
    original_source_name = _get_original_source_name(source)  # e.g. "Apple Watch (Jan)" or "Zepp Life"

    return device_model, software_version, original_source_name


def extract_device_ids(source: SourceInfo | None) -> tuple[str | None, str | None, str | None]:
    """(device_id, source_app_id, device_manufacturer) reported by the SDK.

    Both ids key the data source, so only stable values belong here: iOS and Health Connect never fill
    deviceId (HealthKit's localIdentifier changes per host and on updates). The manufacturer is descriptive.
    """
    if not source:
        return None, None, None
    return source.device_id, _get_source_app_id(source), source.device_manufacturer


def extract_device_type(source: SourceInfo | None) -> DeviceType | None:
    """Device type reported by the SDK, or None when absent or unknown."""
    return map_reported_device_type(source.device_type) if source else None
