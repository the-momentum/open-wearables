"""Device type inference from provider, device model and source name."""

import re
import unicodedata

from app.schemas.enums import DeviceType, ProviderName

from .samsung import SAMSUNG_DEVICE_NAMES

# Providers that only ship a single form factor; model matching is skipped
SINGLE_DEVICE_PROVIDER_TYPE: dict[ProviderName, DeviceType] = {
    ProviderName.OURA: DeviceType.RING,
    ProviderName.ULTRAHUMAN: DeviceType.RING,
    ProviderName.WHOOP: DeviceType.BAND,
}

# Reported device types: mobile SDK deviceType (Health Connect Device.type, incl. extended
# types) and Google Health dataSource.device.formFactor, lowercased
REPORTED_DEVICE_TYPE_MAP: dict[str, DeviceType] = {
    "phone": DeviceType.PHONE,
    "watch": DeviceType.WATCH,
    "ring": DeviceType.RING,
    "scale": DeviceType.SCALE,
    "fitness_band": DeviceType.BAND,
    "chest_strap": DeviceType.CHEST_STRAP,
    "head_mounted": DeviceType.HEAD_MOUNTED,
    "smart_display": DeviceType.SMART_DISPLAY,
    "tablet": DeviceType.TABLET,
    "hearable": DeviceType.HEADPHONES,
    "glasses": DeviceType.GLASSES,
    "fitness_machine": DeviceType.FITNESS_MACHINE,
    "fitness_equipment": DeviceType.FITNESS_MACHINE,
    "consumer_medical_device": DeviceType.OTHER,
    "meter": DeviceType.OTHER,
    "portable_computer": DeviceType.OTHER,
}

# Apple productType codes, case-sensitive
APPLE_PRODUCT_TYPE_PREFIXES: list[tuple[str, DeviceType]] = [
    ("Watch", DeviceType.WATCH),
    ("iPhone", DeviceType.PHONE),
    ("iPad", DeviceType.TABLET),
]

# Samsung model code prefix (SM-X...); SM-R is skipped as it mixes watches, bands and buds
SAMSUNG_MODEL_CODE = re.compile(r"^SM-([A-Z])\d")
SAMSUNG_MODEL_PREFIX_DEVICE_TYPE: dict[str, DeviceType] = {
    "L": DeviceType.WATCH,
    "Q": DeviceType.RING,
    **dict.fromkeys("SAMGFNE", DeviceType.PHONE),
    **dict.fromkeys("XTP", DeviceType.TABLET),
}

# Substrings of the normalized model (lowercased, accents stripped); first match wins, so
# order matters. Keywords starting with \b or ^ are regexes anchored to a word or string start.
DEVICE_MODEL_KEYWORDS: list[tuple[tuple[str, ...], DeviceType]] = [
    ((r"\bpolar h", r"^h(7|9|10)\b", "hrm", "heart rate belt"), DeviceType.CHEST_STRAP),
    (("verity sense", "oh1"), DeviceType.HR_SENSOR),
    (("headphone", "earphone", "suunto wing", "airpods"), DeviceType.HEADPHONES),
    (("index bpm", "blood pressure"), DeviceType.BP_MONITOR),
    (("garmin edge", r"^edge \d"), DeviceType.BIKE_COMPUTER),
    (("watch", "moto 360"), DeviceType.WATCH),
    (("buds",), DeviceType.HEADPHONES),
    (
        (
            "band",
            "vivosmart",
            "vivofit",
            "charge",
            "inspire",
            "luxe",
            "alta",
            "fitbit air",
            "galaxy fit",
            "polar loop",
            "polar 360",
            "index sleep",
        ),
        DeviceType.BAND,
    ),
    ((r"\bring", "oura"), DeviceType.RING),
    (("ipad", "galaxy tab", "pixel tablet"), DeviceType.TABLET),
    (("phone", "pixel", "galaxy", "motorola", "moto "), DeviceType.PHONE),
    (("scale", "index s2"), DeviceType.SCALE),
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
            "approach s",
            "vivoactive",
            "vivomove",
        ),
        DeviceType.WATCH,
    ),
    # Fitbit
    (("versa", "sense", "ionic"), DeviceType.WATCH),
    # Polar
    (("vantage", "grit x", "polar pacer", "pacer pro", "ignite", "unite"), DeviceType.WATCH),
    # Suunto model names always carry the brand ("Suunto Race 2")
    (("suunto",), DeviceType.WATCH),
    (("whoop",), DeviceType.BAND),
]

# Substrings of the normalized source name, for aggregated data without a model
SOURCE_NAME_KEYWORDS: list[tuple[tuple[str, ...], DeviceType]] = [
    (("autosleep",), DeviceType.WATCH),  # AutoSleep requires Apple Watch
    (("mi band", "xiaomi", "amazfit band"), DeviceType.BAND),
    (("oura",), DeviceType.RING),
]


def _keyword_pattern(keywords: tuple[str, ...]) -> re.Pattern[str]:
    return re.compile("|".join(k if k.startswith((r"\b", "^")) else re.escape(k) for k in keywords))


_MODEL_PATTERNS = [(_keyword_pattern(k), t) for k, t in DEVICE_MODEL_KEYWORDS]
_SOURCE_PATTERNS = [(_keyword_pattern(k), t) for k, t in SOURCE_NAME_KEYWORDS]


def _normalize(value: str) -> str:
    """Lowercase and strip accents, so Garmin's "fēnix" / "vívoactive" match."""
    return "".join(c for c in unicodedata.normalize("NFKD", value.lower()) if not unicodedata.combining(c))


# Longest code first, so a regional suffix ("SM-R860N") still finds its base code
_SAMSUNG_CODES = sorted(SAMSUNG_DEVICE_NAMES, key=len, reverse=True)


def _samsung_marketing_name(model_code: str) -> str | None:
    return next((SAMSUNG_DEVICE_NAMES[code] for code in _SAMSUNG_CODES if model_code.startswith(code)), None)


def _match_keywords(value: str, rules: list[tuple[re.Pattern[str], DeviceType]]) -> DeviceType | None:
    for pattern, device_type in rules:
        if pattern.search(value):
            return device_type
    return None


def infer_device_type_from_model(device_model: str | None) -> DeviceType:
    """Infer device type from a device model string (Apple productType codes, Samsung codes, keywords)."""
    if not device_model or device_model.strip().lower() == "unknown":
        return DeviceType.UNKNOWN

    for prefix, device_type in APPLE_PRODUCT_TYPE_PREFIXES:
        if device_model.startswith(prefix):
            return device_type

    if match := SAMSUNG_MODEL_CODE.match(device_model.upper()):
        if device_type := SAMSUNG_MODEL_PREFIX_DEVICE_TYPE.get(match.group(1)):
            return device_type
        # Unmapped prefixes (SM-R) mix watches, bands and buds; resolve listed codes by name
        if name := _samsung_marketing_name(device_model.upper()):
            return _match_keywords(_normalize(name), _MODEL_PATTERNS) or DeviceType.OTHER

    return _match_keywords(_normalize(device_model), _MODEL_PATTERNS) or DeviceType.OTHER


def infer_device_type_from_source_name(source_name: str | None) -> DeviceType:
    """Infer device type from a source/device name (e.g. "Galaxy Watch5", or Zepp Life via Apple Health)."""
    if not source_name:
        return DeviceType.UNKNOWN
    name = _normalize(source_name)
    return _match_keywords(name, _SOURCE_PATTERNS) or _match_keywords(name, _MODEL_PATTERNS) or DeviceType.UNKNOWN


def map_reported_device_type(reported: str | None) -> DeviceType | None:
    """Map an SDK deviceType or Google formFactor to DeviceType; unknown or unmapped values yield None."""
    if not reported:
        return None
    return REPORTED_DEVICE_TYPE_MAP.get(str(reported).lower())


def infer_device_type(
    provider: ProviderName,
    device_model: str | None,
    original_source_name: str | None = None,
    reported_type: DeviceType | None = None,
) -> DeviceType:
    """Resolve device type: single-device provider, then the reported type, then inference."""
    if provider in SINGLE_DEVICE_PROVIDER_TYPE:
        return SINGLE_DEVICE_PROVIDER_TYPE[provider]

    inferred = infer_device_type_from_model(device_model)
    # Cloud providers store their own slug as the source name; it says nothing about the device
    if inferred in (DeviceType.UNKNOWN, DeviceType.OTHER) and (original_source_name or "").lower() != provider.value:
        from_name = infer_device_type_from_source_name(original_source_name)
        if from_name != DeviceType.UNKNOWN:
            inferred = from_name

    if reported_type and reported_type != DeviceType.UNKNOWN:
        # SDKs before the Samsung fix report Galaxy watches as phone; iOS reports iPads as phone
        if reported_type == DeviceType.PHONE and inferred not in (DeviceType.UNKNOWN, DeviceType.OTHER):
            return inferred
        return reported_type

    return inferred
