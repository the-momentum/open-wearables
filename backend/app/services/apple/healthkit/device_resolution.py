"""Device resolution utilities for HealthKit data.

With the simplified DataSource model, we no longer need to create separate Device records.
This module now just extracts device_model and related info from SourceInfo.
"""

from app.schemas.apple.healthkit.source_info import OSVersion, SourceInfo


def _format_os_version(os_version: OSVersion | None) -> str | None:
    """Format OS version as 'major.minor.patch' string."""
    if not os_version:
        return None
    return f"{os_version.major_version}.{os_version.minor_version}.{os_version.patch_version}"


def _get_device_model(product_type: str | None) -> str | None:
    """Return the product type code (e.g., 'iPhone14,5')."""
    if not product_type:
        return None
    return product_type


def extract_device_info(source: SourceInfo | None) -> tuple[str | None, str | None, str | None]:
    """
    Extract device information from SourceInfo.

    Args:
        source: HealthKit SourceInfo object.

    Returns:
        Tuple of (device_model, software_version, manufacturer).
    """
    if not source:
        return None, None, None

    device_model = _get_device_model(source.product_type)
    software_version = _format_os_version(source.operating_system_version)
    manufacturer = source.device_manufacturer or "Apple Inc." if device_model else None

    return device_model, software_version, manufacturer
