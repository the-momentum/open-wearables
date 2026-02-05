"""Tests for ProviderName enum."""

import pytest

from app.schemas.oauth import ProviderName


class TestProviderNameFromSourceString:
    """Test ProviderName.from_source_string() method."""

    @pytest.mark.parametrize(
        ("source", "expected"),
        [
            # Apple variations
            ("apple_health_sdk", ProviderName.APPLE),
            ("Apple Health", ProviderName.APPLE),
            ("APPLE_WATCH", ProviderName.APPLE),
            # Garmin variations
            ("garmin_connect", ProviderName.GARMIN),
            ("Garmin Fenix 7", ProviderName.GARMIN),
            ("GARMIN", ProviderName.GARMIN),
            # Polar variations
            ("polar_flow", ProviderName.POLAR),
            ("Polar Vantage", ProviderName.POLAR),
            ("POLAR", ProviderName.POLAR),
            # Suunto variations
            ("suunto_app", ProviderName.SUUNTO),
            ("Suunto 9", ProviderName.SUUNTO),
            ("SUUNTO", ProviderName.SUUNTO),
            # Whoop variations
            ("whoop_4.0", ProviderName.WHOOP),
            ("Whoop Strap", ProviderName.WHOOP),
            ("WHOOP", ProviderName.WHOOP),
            # Samsung variations
            ("samsung_health", ProviderName.SAMSUNG),
            ("samsung_health_sdk", ProviderName.SAMSUNG),
            ("Samsung Galaxy Watch", ProviderName.SAMSUNG),
            ("SAMSUNG", ProviderName.SAMSUNG),
            # Oura variations
            ("oura_ring", ProviderName.OURA),
            ("Oura Gen 3", ProviderName.OURA),
            ("OURA", ProviderName.OURA),
            # Unknown cases
            ("fitbit", ProviderName.UNKNOWN),
            ("unknown_device", ProviderName.UNKNOWN),
            ("", ProviderName.UNKNOWN),
        ],
    )
    def test_from_source_string_inference(self, source: str, expected: ProviderName) -> None:
        """Should correctly infer provider from source string."""
        assert ProviderName.from_source_string(source) == expected

    def test_from_source_string_none(self) -> None:
        """Should return UNKNOWN for None source."""
        assert ProviderName.from_source_string(None) == ProviderName.UNKNOWN

    def test_from_source_string_case_insensitive(self) -> None:
        """Should be case-insensitive."""
        assert ProviderName.from_source_string("ApPlE") == ProviderName.APPLE
        assert ProviderName.from_source_string("gArMiN") == ProviderName.GARMIN

    def test_from_source_string_partial_match(self) -> None:
        """Should match provider name anywhere in the string."""
        assert ProviderName.from_source_string("my_apple_watch_data") == ProviderName.APPLE
        assert ProviderName.from_source_string("data_from_garmin_device") == ProviderName.GARMIN
