"""Device resolution utilities for HealthKit data."""

from app.schemas.apple.healthkit.sync_request import OSVersion, SourceInfo


def _format_os_version(os_version: OSVersion | None) -> str | None:
    if not os_version:
        return None
    return f"{os_version.major_version}.{os_version.minor_version}.{os_version.patch_version}"

def _get_device_model(source: SourceInfo | None) -> str | None:
    if not source:
        return None
    if source.device_model:
        return source.device_model
    if source.product_type:
        return source.product_type
    return None

def _get_original_source_name(source: SourceInfo | None) -> str | None:
    if not source:
        return None
    if source.name:
        return source.name
    if source.device_name:
        return source.device_name
    return None


def extract_device_info(source: SourceInfo | None) -> tuple[str | None, str | None, str | None]:
    """Extract device information from SourceInfo.

    Returns:
        Tuple of (device_model, software_version, original_source_name).
    """
    if not source:
        return None, None, None

    device_model = _get_device_model(source)
    software_version = _format_os_version(source.operating_system_version)
    original_source_name = _get_original_source_name(source) # e.g. "Apple Watch (Jan)" or "Zepp Life"

    return device_model, software_version, original_source_name
