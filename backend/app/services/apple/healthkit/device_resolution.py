"""Device resolution utilities for HealthKit data."""

from app.schemas.apple.healthkit.sync_request import OSVersion, SourceInfo


def _format_os_version(os_version: OSVersion | None) -> str | None:
    if not os_version:
        return None
    return f"{os_version.major_version}.{os_version.minor_version}.{os_version.patch_version}"


def _get_device_model(product_type: str | None) -> str | None:
    if not product_type:
        return None
    return product_type


def extract_device_info(source: SourceInfo | None) -> tuple[str | None, str | None, str | None]:
    """Extract device information from SourceInfo.

    Returns:
        Tuple of (device_model, software_version, original_source_name).
    """
    if not source:
        return None, None, None

    device_model = _get_device_model(source.product_type)
    software_version = _format_os_version(source.operating_system_version)
    original_source_name = source.name  # e.g. "Apple Watch (Jan)" or "Zepp Life"

    return device_model, software_version, original_source_name
