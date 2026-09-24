"""Tests for device type inference."""

import pytest

from app.constants.devices_map import infer_device_type, infer_device_type_from_model, map_sdk_device_type
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
            ("Pixel 8", DeviceType.PHONE),
            ("Pixel Watch 2", DeviceType.WATCH),
            ("Galaxy Watch7", DeviceType.WATCH),
            ("Galaxy Fit3", DeviceType.BAND),
            ("Galaxy Buds2 Pro", DeviceType.OTHER),
            ("motorola edge 60 pro", DeviceType.PHONE),
            ("Charge 4", DeviceType.BAND),
            ("Inspire 3", DeviceType.BAND),
            ("Google Fitbit Air", DeviceType.BAND),
            ("Versa 4", DeviceType.WATCH),
            ("Fitbit Sense 2", DeviceType.WATCH),
            ("Polar Loop Gen 2", DeviceType.BAND),
            ("Polar 360", DeviceType.BAND),
            ("Polar Vantage M3", DeviceType.WATCH),
            ("Polar H10", DeviceType.OTHER),
            ("Polar Verity Sense", DeviceType.OTHER),
            ("Garmin fenix 8 Pro", DeviceType.WATCH),
            ("Garmin vivoactive 5", DeviceType.WATCH),
            ("Garmin Edge 1030", DeviceType.OTHER),
            ("HRM-Pro Plus", DeviceType.OTHER),
            ("Garmin Index S2", DeviceType.SCALE),
            ("Suunto Race 2", DeviceType.WATCH),
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
            (ProviderName.SUUNTO, DeviceType.WATCH),
            (ProviderName.GARMIN, DeviceType.UNKNOWN),
        ],
    )
    def test_provider_default_without_model(self, provider: ProviderName, expected: DeviceType) -> None:
        assert infer_device_type(provider, None) == expected

    def test_single_device_provider_skips_model_matching(self) -> None:
        assert infer_device_type(ProviderName.OURA, "Galaxy Watch7") == DeviceType.RING

    def test_provider_default_replaces_other(self) -> None:
        assert infer_device_type(ProviderName.SUUNTO, "Ambit3") == DeviceType.WATCH
        assert infer_device_type(ProviderName.GARMIN, "Garmin Edge 1030") == DeviceType.OTHER


class TestReportedDeviceType:
    @pytest.mark.parametrize(
        ("sdk_value", "expected"),
        [
            ("fitness_band", DeviceType.BAND),
            ("chest_strap", DeviceType.OTHER),
            ("unknown", None),
            (None, None),
        ],
    )
    def test_map_sdk_device_type(self, sdk_value: str | None, expected: DeviceType | None) -> None:
        assert map_sdk_device_type(sdk_value) == expected

    def test_sdk_type_wins_over_inference(self) -> None:
        assert infer_device_type(ProviderName.SAMSUNG, "cybert-model", "cybert", DeviceType.PHONE) == DeviceType.PHONE
        assert infer_device_type(ProviderName.HEALTH_CONNECT, "Pixel 8", None, DeviceType.WATCH) == DeviceType.WATCH

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
