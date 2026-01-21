from app.database import DbSession
from app.repositories.device_repository import DeviceRepository
from app.schemas.apple.healthkit.source_info import OSVersion, SourceInfo

# Mapping from Apple productType codes to real device names
APPLE_DEVICE_NAMES = {
    # iPhones
    "iPhone1,1": "iPhone",
    "iPhone1,2": "iPhone 3G",
    "iPhone2,1": "iPhone 3GS",
    "iPhone3,1": "iPhone 4",
    "iPhone3,2": "iPhone 4 GSM Rev A",
    "iPhone3,3": "iPhone 4 CDMA",
    "iPhone4,1": "iPhone 4S",
    "iPhone5,1": "iPhone 5 (GSM)",
    "iPhone5,2": "iPhone 5 (GSM+CDMA)",
    "iPhone5,3": "iPhone 5C (GSM)",
    "iPhone5,4": "iPhone 5C (Global)",
    "iPhone6,1": "iPhone 5S (GSM)",
    "iPhone6,2": "iPhone 5S (Global)",
    "iPhone7,1": "iPhone 6 Plus",
    "iPhone7,2": "iPhone 6",
    "iPhone8,1": "iPhone 6s",
    "iPhone8,2": "iPhone 6s Plus",
    "iPhone8,4": "iPhone SE (GSM)",
    "iPhone9,1": "iPhone 7",
    "iPhone9,2": "iPhone 7 Plus",
    "iPhone9,3": "iPhone 7",
    "iPhone9,4": "iPhone 7 Plus",
    "iPhone10,1": "iPhone 8",
    "iPhone10,2": "iPhone 8 Plus",
    "iPhone10,3": "iPhone X Global",
    "iPhone10,4": "iPhone 8",
    "iPhone10,5": "iPhone 8 Plus",
    "iPhone10,6": "iPhone X GSM",
    "iPhone11,2": "iPhone XS",
    "iPhone11,4": "iPhone XS Max",
    "iPhone11,6": "iPhone XS Max Global",
    "iPhone11,8": "iPhone XR",
    "iPhone12,1": "iPhone 11",
    "iPhone12,3": "iPhone 11 Pro",
    "iPhone12,5": "iPhone 11 Pro Max",
    "iPhone12,8": "iPhone SE 2nd Gen",
    "iPhone13,1": "iPhone 12 Mini",
    "iPhone13,2": "iPhone 12",
    "iPhone13,3": "iPhone 12 Pro",
    "iPhone13,4": "iPhone 12 Pro Max",
    "iPhone14,2": "iPhone 13 Pro",
    "iPhone14,3": "iPhone 13 Pro Max",
    "iPhone14,4": "iPhone 13 Mini",
    "iPhone14,5": "iPhone 13",
    "iPhone14,6": "iPhone SE 3rd Gen",
    "iPhone14,7": "iPhone 14",
    "iPhone14,8": "iPhone 14 Plus",
    "iPhone15,2": "iPhone 14 Pro",
    "iPhone15,3": "iPhone 14 Pro Max",
    "iPhone15,4": "iPhone 15",
    "iPhone15,5": "iPhone 15 Plus",
    "iPhone16,1": "iPhone 15 Pro",
    "iPhone16,2": "iPhone 15 Pro Max",
    "iPhone17,1": "iPhone 16 Pro",
    "iPhone17,2": "iPhone 16 Pro Max",
    "iPhone17,3": "iPhone 16",
    "iPhone17,4": "iPhone 16 Plus",
    "iPhone17,5": "iPhone 16e",
    "iPhone18,1": "iPhone 17 Pro",
    "iPhone18,2": "iPhone 17 Pro Max",
    "iPhone18,3": "iPhone 17",
    "iPhone18,4": "iPhone Air",
    # Apple Watch
    "Watch1,1": "Apple Watch 38mm",
    "Watch1,2": "Apple Watch 42mm",
    "Watch2,6": "Apple Watch Series 1 38mm",
    "Watch2,7": "Apple Watch Series 1 42mm",
    "Watch2,3": "Apple Watch Series 2 38mm",
    "Watch2,4": "Apple Watch Series 2 42mm",
    "Watch3,1": "Apple Watch Series 3 38mm (GPS+Cellular)",
    "Watch3,2": "Apple Watch Series 3 42mm (GPS+Cellular)",
    "Watch3,3": "Apple Watch Series 3 38mm (GPS)",
    "Watch3,4": "Apple Watch Series 3 42mm (GPS)",
    "Watch4,1": "Apple Watch Series 4 40mm (GPS)",
    "Watch4,2": "Apple Watch Series 4 44mm (GPS)",
    "Watch4,3": "Apple Watch Series 4 40mm (GPS+Cellular)",
    "Watch4,4": "Apple Watch Series 4 44mm (GPS+Cellular)",
    "Watch5,1": "Apple Watch Series 5 40mm (GPS)",
    "Watch5,2": "Apple Watch Series 5 44mm (GPS)",
    "Watch5,3": "Apple Watch Series 5 40mm (GPS+Cellular)",
    "Watch5,4": "Apple Watch Series 5 44mm (GPS+Cellular)",
    "Watch5,9": "Apple Watch SE 40mm (GPS)",
    "Watch5,10": "Apple Watch SE 44mm (GPS)",
    "Watch5,11": "Apple Watch SE 40mm (GPS+Cellular)",
    "Watch5,12": "Apple Watch SE 44mm (GPS+Cellular)",
    "Watch6,1": "Apple Watch Series 6 40mm (GPS)",
    "Watch6,2": "Apple Watch Series 6 44mm (GPS)",
    "Watch6,3": "Apple Watch Series 6 40mm (GPS+Cellular)",
    "Watch6,4": "Apple Watch Series 6 44mm (GPS+Cellular)",
    "Watch6,6": "Apple Watch Series 7 41mm (GPS)",
    "Watch6,7": "Apple Watch Series 7 45mm (GPS)",
    "Watch6,8": "Apple Watch Series 7 41mm (GPS+Cellular)",
    "Watch6,9": "Apple Watch Series 7 45mm (GPS+Cellular)",
    "Watch6,10": "Apple Watch SE 40mm (GPS)",
    "Watch6,11": "Apple Watch SE 44mm (GPS)",
    "Watch6,12": "Apple Watch SE 40mm (GPS+Cellular)",
    "Watch6,13": "Apple Watch SE 44mm (GPS+Cellular)",
    "Watch6,14": "Apple Watch Series 8 41mm (GPS)",
    "Watch6,15": "Apple Watch Series 8 45mm (GPS)",
    "Watch6,16": "Apple Watch Series 8 41mm (GPS+Cellular)",
    "Watch6,17": "Apple Watch Series 8 45mm (GPS+Cellular)",
    "Watch6,18": "Apple Watch Ultra",
    "Watch7,1": "Apple Watch Series 9 41mm (GPS)",
    "Watch7,2": "Apple Watch Series 9 45mm (GPS)",
    "Watch7,3": "Apple Watch Series 9 41mm (GPS+Cellular)",
    "Watch7,4": "Apple Watch Series 9 45mm (GPS+Cellular)",
    "Watch7,5": "Apple Watch Ultra 2",
    "Watch7,8": "Apple Watch Series 10 42mm (GPS)",
    "Watch7,9": "Apple Watch Series 10 46mm (GPS)",
    "Watch7,10": "Apple Watch Series 10 42mm (GPS+Cellular)",
    "Watch7,11": "Apple Watch Series 10 46mm (GPS+Cellular)",
    "Watch7,12": "Apple Watch Ultra 3 49mm",
    "Watch7,13": "Apple Watch SE 3 40mm",
    "Watch7,14": "Apple Watch SE 3 44mm",
    "Watch7,15": "Apple Watch SE 3 40mm (GPS+Cellular)",
    "Watch7,16": "Apple Watch SE 3 44mm (GPS+Cellular)",
    "Watch7,17": "Apple Watch Series 11 42mm",
    "Watch7,18": "Apple Watch Series 11 46mm",
    "Watch7,19": "Apple Watch Series 11 42mm (GPS+Cellular)",
    "Watch7,20": "Apple Watch Series 11 46mm (GPS+Cellular)",
    # iPads (common models)
    "iPad1,1": "iPad",
    "iPad2,1": "iPad 2nd Gen",
    "iPad2,5": "iPad mini",
    "iPad3,1": "iPad 3rd Gen",
    "iPad3,4": "iPad 4th Gen",
    "iPad4,1": "iPad Air",
    "iPad4,4": "iPad mini Retina",
    "iPad5,1": "iPad mini 4",
    "iPad5,3": "iPad Air 2",
    "iPad6,3": "iPad Pro 9.7-inch",
    "iPad6,7": "iPad Pro 12.9-inch",
    "iPad6,11": "iPad (2017)",
    "iPad7,1": "iPad Pro 12.9-inch 2nd Gen",
    "iPad7,3": "iPad Pro 10.5-inch",
    "iPad7,5": "iPad 6th Gen",
    "iPad7,11": "iPad 7th Gen",
    "iPad8,1": "iPad Pro 11-inch 3rd Gen",
    "iPad8,5": "iPad Pro 12.9-inch 3rd Gen",
    "iPad8,9": "iPad Pro 11-inch 4th Gen",
    "iPad8,11": "iPad Pro 12.9-inch 4th Gen",
    "iPad11,1": "iPad mini 5th Gen",
    "iPad11,3": "iPad Air 3rd Gen",
    "iPad11,6": "iPad 8th Gen",
    "iPad12,1": "iPad 9th Gen",
    "iPad13,1": "iPad Air 4th Gen",
    "iPad13,4": "iPad Pro 11-inch 5th Gen",
    "iPad13,8": "iPad Pro 12.9-inch 5th Gen",
    "iPad13,16": "iPad Air 5th Gen",
    "iPad13,18": "iPad 10th Gen",
    "iPad14,1": "iPad mini 6th Gen",
    "iPad14,3": "iPad Pro 11-inch 4th Gen",
    "iPad14,5": "iPad Pro 12.9-inch 6th Gen",
    "iPad14,8": "iPad Air 11-inch 6th Gen",
    "iPad14,10": "iPad Air 13-inch 6th Gen",
    "iPad15,3": "iPad Air 11-inch 7th Gen",
    "iPad15,5": "iPad Air 13-inch 7th Gen",
    "iPad15,7": "iPad 11th Gen",
    "iPad16,1": "iPad mini 7th Gen",
    "iPad16,3": "iPad Pro 11-inch 5th Gen",
    "iPad16,5": "iPad Pro 12.9-inch 7th Gen",
    # iPods
    "iPod1,1": "iPod 1st Gen",
    "iPod2,1": "iPod 2nd Gen",
    "iPod3,1": "iPod 3rd Gen",
    "iPod4,1": "iPod 4th Gen",
    "iPod5,1": "iPod 5th Gen",
    "iPod7,1": "iPod 6th Gen",
    "iPod9,1": "iPod 7th Gen",
}


def _format_os_version(os_version: OSVersion | None) -> str | None:
    """Format OS version as 'major.minor.patch' string."""
    if not os_version:
        return None
    return f"{os_version.majorVersion}.{os_version.minorVersion}.{os_version.patchVersion}"


def _get_device_name(product_type: str | None) -> str:
    """Get real device name from productType code."""
    if not product_type:
        return "Unknown Device"
    return APPLE_DEVICE_NAMES.get(product_type, product_type)


def resolve_device(
    db: DbSession,
    device_repo: DeviceRepository,
    source: SourceInfo | None,
    fallback_name: str | None,
) -> str | None:
    if not source:
        return fallback_name

    serial_number = source.bundleIdentifier or ""
    provider_name = source.deviceManufacturer or "Apple Inc."
    name = _get_device_name(source.productType)
    sw_version = _format_os_version(source.operatingSystemVersion)

    if serial_number or source.productType:
        device_repo.ensure_device(
            db,
            provider_name=provider_name,
            serial_number=serial_number,
            name=name,
            sw_version=sw_version,
        )

        return source.productType

    return fallback_name
