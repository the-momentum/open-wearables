"""Tests for device type inference."""

import pytest

from app.constants.devices_map import infer_device_type, infer_device_type_from_model, map_reported_device_type
from app.schemas.enums import DeviceType, ProviderName


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
            ("Garmin Index Sleep Monitor", DeviceType.BAND),
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
