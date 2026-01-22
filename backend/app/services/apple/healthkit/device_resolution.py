from app.database import DbSession
from app.repositories.device_repository import DeviceRepository
from app.schemas.apple.healthkit.source_info import OSVersion, SourceInfo


def _format_os_version(os_version: OSVersion | None) -> str | None:
    """Format OS version as 'major.minor.patch' string."""
    if not os_version:
        return None
    return f"{os_version.major_version}.{os_version.minor_version}.{os_version.patch_version}"


def _get_device_name(product_type: str | None) -> str:
    """Return the original productType code (e.g., 'iPhone14,5')."""
    if not product_type:
        return "Unknown Device"
    return product_type


def resolve_device(
    db: DbSession,
    device_repo: DeviceRepository,
    source: SourceInfo | None,
    fallback_name: str | None,
) -> str | None:
    if not source:
        return fallback_name

    serial_number = source.bundle_identifier or ""
    provider_name = source.device_manufacturer or "Apple Inc."
    name = _get_device_name(source.product_type)
    sw_version = _format_os_version(source.operating_system_version)

    if serial_number or source.product_type:
        device_repo.ensure_device(
            db,
            provider_name=provider_name,
            serial_number=serial_number,
            name=name,
            sw_version=sw_version,
        )

        return source.product_type

    return fallback_name
