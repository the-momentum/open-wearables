"""Device type inference from provider, device model and source name."""

import re

from app.schemas.enums import DeviceType, ProviderName

# Providers that only ship a single form factor; model matching is skipped
SINGLE_DEVICE_PROVIDER_TYPE: dict[ProviderName, DeviceType] = {
    ProviderName.OURA: DeviceType.RING,
    ProviderName.ULTRAHUMAN: DeviceType.RING,
    ProviderName.WHOOP: DeviceType.BAND,
}

# Fallback when the model is unknown or unmatched
PROVIDER_DEFAULT_DEVICE_TYPE: dict[ProviderName, DeviceType] = {
    ProviderName.SUUNTO: DeviceType.WATCH,
}

# Device type reported by the mobile SDKs (Health Connect / Samsung / HealthKit)
SDK_DEVICE_TYPE_MAP: dict[str, DeviceType] = {
    "phone": DeviceType.PHONE,
    "watch": DeviceType.WATCH,
    "ring": DeviceType.RING,
    "scale": DeviceType.SCALE,
    "fitness_band": DeviceType.BAND,
    "chest_strap": DeviceType.OTHER,
    "head_mounted": DeviceType.OTHER,
    "smart_display": DeviceType.OTHER,
}

# Apple productType codes, case-sensitive; iPad is treated as phone for priority purposes
APPLE_PRODUCT_TYPE_PREFIXES: list[tuple[str, DeviceType]] = [
    ("Watch", DeviceType.WATCH),
    ("iPhone", DeviceType.PHONE),
    ("iPad", DeviceType.PHONE),
]

# Samsung model code prefix (SM-X...); SM-R is skipped as it mixes watches, bands and buds
SAMSUNG_MODEL_CODE = re.compile(r"^SM-([A-Z])\d")
SAMSUNG_MODEL_PREFIX_DEVICE_TYPE: dict[str, DeviceType] = {
    "L": DeviceType.WATCH,
    "Q": DeviceType.RING,
    **dict.fromkeys("SAMGFNEXTP", DeviceType.PHONE),
}

WEARABLE_DEVICE_TYPES = frozenset({DeviceType.WATCH, DeviceType.BAND, DeviceType.RING, DeviceType.SCALE})

# Substrings of the lowercased model; first match wins, so order matters
DEVICE_MODEL_KEYWORDS: list[tuple[tuple[str, ...], DeviceType]] = [
    # Sensors, straps and earbuds
    (("verity sense", "polar h", "oh1", "hrm", "buds"), DeviceType.OTHER),
    (("watch",), DeviceType.WATCH),
    (
        ("band", "vivosmart", "vivofit", "charge", "inspire", "luxe", "alta", "fitbit air", "galaxy fit"),
        DeviceType.BAND,
    ),
    (("loop", "polar 360"), DeviceType.BAND),
    (("ring", "oura"), DeviceType.RING),
    (("phone", "pixel", "galaxy", "motorola", "moto "), DeviceType.PHONE),
    (("scale", "index"), DeviceType.SCALE),
    # Garmin
    (
        (
            "forerunner",
            "fenix",
            "venu",
            "epix",
            "enduro",
            "instinct",
            "tactix",
            "approach",
            "vivoactive",
            "vivomove",
        ),
        DeviceType.WATCH,
    ),
    # Fitbit
    (("versa", "sense", "ionic"), DeviceType.WATCH),
    # Polar
    (("vantage", "grit x", "pacer", "ignite", "unite"), DeviceType.WATCH),
    # Suunto
    (("suunto", "vertical", "race", "peak"), DeviceType.WATCH),
    (("whoop",), DeviceType.BAND),
]

# Substrings of the lowercased source name, for aggregated data without a model
SOURCE_NAME_KEYWORDS: list[tuple[tuple[str, ...], DeviceType]] = [
    (("autosleep",), DeviceType.WATCH),  # AutoSleep requires Apple Watch
    (("mi band", "xiaomi", "amazfit band"), DeviceType.BAND),
    (("oura",), DeviceType.RING),
]


def _match_keywords(value: str, rules: list[tuple[tuple[str, ...], DeviceType]]) -> DeviceType | None:
    for keywords, device_type in rules:
        if any(keyword in value for keyword in keywords):
            return device_type
    return None


def infer_device_type_from_model(device_model: str | None) -> DeviceType:
    """Infer device type from a device model string (Apple productType codes, Samsung codes, keywords)."""
    if not device_model or device_model.strip().lower() == "unknown":
        return DeviceType.UNKNOWN

    for prefix, device_type in APPLE_PRODUCT_TYPE_PREFIXES:
        if device_model.startswith(prefix):
            return device_type

    if (match := SAMSUNG_MODEL_CODE.match(device_model.upper())) and (
        device_type := SAMSUNG_MODEL_PREFIX_DEVICE_TYPE.get(match.group(1))
    ):
        return device_type

    return _match_keywords(device_model.lower(), DEVICE_MODEL_KEYWORDS) or DeviceType.OTHER


def infer_device_type_from_source_name(source_name: str | None) -> DeviceType:
    """Infer device type from a source/device name (e.g. "Galaxy Watch5", or Zepp Life via Apple Health)."""
    if not source_name:
        return DeviceType.UNKNOWN
    name_lower = source_name.lower()
    return (
        _match_keywords(name_lower, SOURCE_NAME_KEYWORDS)
        or _match_keywords(name_lower, DEVICE_MODEL_KEYWORDS)
        or DeviceType.UNKNOWN
    )


def map_sdk_device_type(sdk_device_type: str | None) -> DeviceType | None:
    """Map a mobile SDK deviceType to DeviceType; unknown or unmapped values yield None."""
    if not sdk_device_type:
        return None
    return SDK_DEVICE_TYPE_MAP.get(str(sdk_device_type).lower())


def infer_device_type(
    provider: ProviderName,
    device_model: str | None,
    original_source_name: str | None = None,
    reported_type: DeviceType | None = None,
) -> DeviceType:
    """Resolve device type: single-device provider, then the SDK-reported type, then inference."""
    if provider in SINGLE_DEVICE_PROVIDER_TYPE:
        return SINGLE_DEVICE_PROVIDER_TYPE[provider]

    inferred = infer_device_type_from_model(device_model)
    if inferred in (DeviceType.UNKNOWN, DeviceType.OTHER):
        from_name = infer_device_type_from_source_name(original_source_name)
        if from_name != DeviceType.UNKNOWN:
            inferred = from_name

    if reported_type and reported_type != DeviceType.UNKNOWN:
        # SDKs before the Samsung fix report Galaxy watches as phone
        if reported_type == DeviceType.PHONE and inferred in WEARABLE_DEVICE_TYPES:
            return inferred
        return reported_type

    if inferred in (DeviceType.UNKNOWN, DeviceType.OTHER) and provider in PROVIDER_DEFAULT_DEVICE_TYPE:
        return PROVIDER_DEFAULT_DEVICE_TYPE[provider]
    return inferred
