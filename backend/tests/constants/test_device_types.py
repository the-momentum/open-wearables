"""Tests for device type inference."""

import pytest

from app.constants.devices_map import (
    infer_device_type,
    infer_device_type_from_model,
    is_host_model,
    map_reported_device_type,
    normalize_device_model,
)
from app.schemas.enums import DeviceType, ProviderName
from app.schemas.providers.mobile_sdk import SourceInfo
from app.services.sdk.device_resolution import extract_device_info, extract_device_type


class TestInferDeviceTypeFromModel:
    @pytest.mark.parametrize(
        ("device_model", "expected"),
        [
            (None, DeviceType.UNKNOWN),
            ("unknown", DeviceType.UNKNOWN),
            ("Watch6,12", DeviceType.WATCH),
            ("iPhone15,2", DeviceType.PHONE),
            ("SM-L315F", DeviceType.WATCH),
            ("SM-Q507", DeviceType.RING),
            ("SM-M127F", DeviceType.PHONE),
            ("SM-S911B", DeviceType.PHONE),
            ("SM-R390", DeviceType.OTHER),
            ("SM-R860", DeviceType.WATCH),
            ("SM-R860N", DeviceType.WATCH),
            ("Pixel 8", DeviceType.PHONE),
            ("Pixel Watch 2", DeviceType.WATCH),
            ("Galaxy Watch7", DeviceType.WATCH),
            ("Galaxy Fit3", DeviceType.BAND),
            ("Galaxy Buds2 Pro", DeviceType.HEADPHONES),
            ("motorola edge 60 pro", DeviceType.PHONE),
            ("Charge 4", DeviceType.BAND),
            ("Inspire 3", DeviceType.BAND),
            ("Google Fitbit Air", DeviceType.BAND),
            ("Versa 4", DeviceType.WATCH),
            ("Fitbit Sense 2", DeviceType.WATCH),
            ("Polar Loop Gen 2", DeviceType.BAND),
            ("Polar 360", DeviceType.BAND),
            ("Polar Vantage M3", DeviceType.WATCH),
            ("Polar H10", DeviceType.CHEST_STRAP),
            ("Polar Verity Sense", DeviceType.HR_SENSOR),
            ("Garmin fenix 8 Pro", DeviceType.WATCH),
            ("Garmin vivoactive 5", DeviceType.WATCH),
            ("Garmin Edge 1030", DeviceType.BIKE_COMPUTER),
            ("HRM-Pro Plus", DeviceType.CHEST_STRAP),
            ("Garmin Index S2", DeviceType.SCALE),
            ("Suunto Race 2", DeviceType.WATCH),
            ("Moto 360", DeviceType.WATCH),
            ("H10", DeviceType.CHEST_STRAP),
            ("Edge 540", DeviceType.BIKE_COMPUTER),
            ("iPad13,1", DeviceType.TABLET),
            ("SM-X710", DeviceType.TABLET),
            ("Galaxy Tab S9", DeviceType.TABLET),
            ("Suunto Wing 2 Bone Conduction Headphone", DeviceType.HEADPHONES),
            ("Garmin Index BPM", DeviceType.BP_MONITOR),
            ("Garmin Index Sleep Monitor", DeviceType.SLEEP_MONITOR),
            ("Garmin fēnix 8", DeviceType.WATCH),
            ("Garmin vívoactive 6", DeviceType.WATCH),
            ("Garmin Approach G80", DeviceType.OTHER),
            ("Garmin Approach S70", DeviceType.WATCH),
            ("Huawei Watch Buds", DeviceType.WATCH),
            ("Galaxy Ring", DeviceType.RING),
            ("Suunto Smart Heart Rate Belt", DeviceType.CHEST_STRAP),
        ],
    )
    def test_infers_type(self, device_model: str | None, expected: DeviceType) -> None:
        assert infer_device_type_from_model(device_model) == expected


class TestInferDeviceType:
    @pytest.mark.parametrize(
        ("provider", "expected"),
        [
            (ProviderName.OURA, DeviceType.RING),
            (ProviderName.ULTRAHUMAN, DeviceType.RING),
            (ProviderName.WHOOP, DeviceType.BAND),
            (ProviderName.SUUNTO, DeviceType.UNKNOWN),
            (ProviderName.GARMIN, DeviceType.UNKNOWN),
        ],
    )
    def test_provider_default_without_model(self, provider: ProviderName, expected: DeviceType) -> None:
        assert infer_device_type(provider, None) == expected

    def test_single_device_provider_skips_model_matching(self) -> None:
        assert infer_device_type(ProviderName.OURA, "Galaxy Watch7") == DeviceType.RING

    def test_suunto_resolves_from_gear_model(self) -> None:
        assert infer_device_type(ProviderName.SUUNTO, "Suunto Race 2") == DeviceType.WATCH
        assert infer_device_type(ProviderName.SUUNTO, "Polar H10") == DeviceType.CHEST_STRAP

    @pytest.mark.parametrize("source_name", ["Loop", "Pacer", "Sleep Monitoring", "Bracelet"])
    def test_app_and_word_substrings_are_not_devices(self, source_name: str) -> None:
        assert infer_device_type(ProviderName.APPLE, None, source_name) == DeviceType.UNKNOWN

    def test_provider_slug_source_is_not_a_device_name(self) -> None:
        assert infer_device_type(ProviderName.SUUNTO, None, "suunto") == DeviceType.UNKNOWN

    def test_unmatched_model_stays_other(self) -> None:
        assert infer_device_type(ProviderName.GARMIN, "Garmin Varia RTL515") == DeviceType.OTHER


class TestReportedDeviceType:
    @pytest.mark.parametrize(
        ("sdk_value", "expected"),
        [
            ("fitness_band", DeviceType.BAND),
            ("chest_strap", DeviceType.CHEST_STRAP),
            ("hearable", DeviceType.HEADPHONES),
            ("TABLET", DeviceType.TABLET),
            ("FORM_FACTOR_UNSPECIFIED", None),
            ("unknown", None),
            (None, None),
        ],
    )
    def test_map_reported_device_type(self, sdk_value: str | None, expected: DeviceType | None) -> None:
        assert map_reported_device_type(sdk_value) == expected

    def test_sdk_type_wins_over_inference(self) -> None:
        assert infer_device_type(ProviderName.SAMSUNG, "cybert-model", "cybert", DeviceType.PHONE) == DeviceType.PHONE
        assert infer_device_type(ProviderName.HEALTH_CONNECT, "Pixel 8", None, DeviceType.WATCH) == DeviceType.WATCH

    def test_specific_inference_overrides_reported_other(self) -> None:
        assert (
            infer_device_type(ProviderName.SAMSUNG, "Garmin Index BPM", None, DeviceType.OTHER) == DeviceType.BP_MONITOR
        )
        assert infer_device_type(ProviderName.SAMSUNG, "unlisted-model", None, DeviceType.OTHER) == DeviceType.OTHER

    def test_relaying_host_is_ignored_for_third_party_writer(self) -> None:
        oura = infer_device_type(ProviderName.APPLE, "iPhone16,1", "Oura", DeviceType.PHONE, "com.ouraring.oura")
        strava = infer_device_type(ProviderName.APPLE, "iPhone16,1", "Strava", DeviceType.PHONE, "com.strava.run")
        assert (oura, strava) == (DeviceType.RING, DeviceType.UNKNOWN)

    def test_unknown_sdk_type_falls_back_to_inference(self) -> None:
        assert infer_device_type(ProviderName.HEALTH_CONNECT, "Pixel 8", None, DeviceType.UNKNOWN) == DeviceType.PHONE

    @pytest.mark.parametrize(
        ("device_model", "name"),
        [
            ("SM-L315F", "Galaxy Watch7"),
            ("SM-R930", "Galaxy Watch6"),
        ],
    )
    def test_samsung_watch_resolves_same_before_and_after_sdk_fix(self, device_model: str, name: str) -> None:
        old_sdk = infer_device_type(ProviderName.SAMSUNG, device_model, name, DeviceType.PHONE)
        new_sdk = infer_device_type(ProviderName.SAMSUNG, device_model, name, DeviceType.WATCH)
        assert old_sdk == new_sdk == DeviceType.WATCH


@pytest.mark.parametrize(
    ("raw", "expected"), [("unknown", None), ("  ", None), (None, None), (" Garmin fenix 8 ", "Garmin fenix 8")]
)
def test_normalize_device_model(raw: str | None, expected: str | None) -> None:
    assert normalize_device_model(raw) == expected


@pytest.mark.parametrize(
    ("app_id", "device_model", "hardware", "expected"),
    [
        ("com.apple.health.0BA80355-AAAA", "iPhone16,1", "Watch6,2", "Watch6,2"),
        ("com.apple.health.0BA80355-AAAA", "iPhone16,1", None, "iPhone16,1"),
        ("com.apple.BTLEServer", "Watch7,9", "00760690.03", None),
        ("com.ouraring.oura", "iPhone15,2", "iPhone15,2", None),
        ("com.ouraring.oura", "Oura Ring Gen3", None, "Oura Ring Gen3"),
    ],
)
def test_sdk_device_model_uses_hardware_only_for_apple_own_sources(
    app_id: str, device_model: str, hardware: str | None, expected: str | None
) -> None:
    source = SourceInfo(app_id=app_id, device_model=device_model, device_hardware_version=hardware)
    assert extract_device_info(source, ProviderName.APPLE)[0] == expected


def test_sdk_drops_relaying_host_model_of_third_party_writer() -> None:
    relayed = SourceInfo(app_id="com.ouraring.oura", name="Oura", device_model="iPhone16,1")
    assert extract_device_info(relayed, ProviderName.APPLE)[0] is None


@pytest.mark.parametrize(
    ("app_id", "name", "device_model"),
    [
        ("com.garmin.connect.mobile", "Connect", "iPhone16,1"),
        ("com.apple.shortcuts", "Shortcuts", "Watch7,9"),
        # Cronometer attaches the local iPhone as its HKDevice, so even fixed SDKs send it
        ("CRONOMETER-GOLD", "Cronometer", "iPhone"),
    ],
)
def test_sdk_drops_relaying_host_type_of_third_party_writer(app_id: str, name: str, device_model: str) -> None:
    relayed = SourceInfo(app_id=app_id, name=name, device_model=device_model, device_type="phone")
    model, _, source_name = extract_device_info(relayed, ProviderName.APPLE)
    reported = extract_device_type(relayed, ProviderName.APPLE)
    assert reported is None
    assert infer_device_type(ProviderName.APPLE, model, source_name, reported, app_id) == DeviceType.UNKNOWN


def test_sdk_keeps_reported_type_of_apple_own_source() -> None:
    watch = SourceInfo(app_id="com.apple.health.0BA80355-AAAA", device_model="Watch7,5", device_type="watch")
    assert extract_device_type(watch, ProviderName.APPLE) == DeviceType.WATCH


def test_sdk_keeps_apple_prefixed_model_outside_healthkit() -> None:
    """Only HealthKit relays through a host, so a Health Connect "Watch GT 3" is the producing device."""
    huawei = SourceInfo(app_id="com.huawei.health", device_model="Watch GT 3", device_type="watch")
    assert extract_device_info(huawei, ProviderName.HEALTH_CONNECT)[0] == "Watch GT 3"
    assert extract_device_type(huawei, ProviderName.HEALTH_CONNECT) == DeviceType.WATCH
    assert not is_host_model(ProviderName.HEALTH_CONNECT, "com.huawei.health", "Watch GT 3")


@pytest.mark.parametrize(
    ("device_model", "expected"),
    [
        ("iPhone16,1", True),
        ("Watch7,9", True),
        ("iPad13,1", True),
        ("iPod9,1", True),
        ("iPhone", True),
        ("Watch", True),
        ("iPod touch", True),
        # "Watch" is generic: another brand's watch is the producing device
        ("Watch GT 3", False),
        ("H10", False),
    ],
)
def test_host_model_matches_apple_hardware_only(device_model: str, expected: bool) -> None:
    assert is_host_model(ProviderName.APPLE, "com.huawei.health", device_model) is expected
