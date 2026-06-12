"""Tests for the centralized unit conversion service.

Pure unit tests (no database). They verify that incoming provider values are converted to
canonical units, including the per-provider default-source-unit fallback used when the unit
string is absent, and the log+skip signal (``None``) for unrecognized units.
"""

from decimal import Decimal

import pytest

from app.schemas.enums import SeriesType
from app.services.unit_conversion import UnitConversionService, unit_conversion_service


class TestUnitConversionHeight:
    """Height is reported in meters by every SDK provider -> stored as centimeters."""

    @pytest.mark.parametrize("provider", ["apple", "google", "samsung"])
    def test_height_meters_to_cm_unit_absent(self, provider: str) -> None:
        result = unit_conversion_service.convert(SeriesType.height, Decimal("1.7526"), provider, unit="")
        # Exact Decimal scale must be preserved (1.7526 * 100 == 175.2600).
        assert str(result) == "175.2600"

    def test_height_explicit_meters_unit(self) -> None:
        result = unit_conversion_service.convert(SeriesType.height, Decimal("1.7526"), "apple", unit="meters")
        assert str(result) == "175.2600"


class TestUnitConversionBodyFat:
    """Body fat is a 0..1 ratio on Apple but already a percent on Health Connect."""

    def test_apple_body_fat_ratio_scaled(self) -> None:
        result = unit_conversion_service.convert(SeriesType.body_fat_percentage, Decimal("0.304"), "apple", unit="")
        assert str(result) == "30.400"

    def test_google_body_fat_not_scaled(self) -> None:
        result = unit_conversion_service.convert(SeriesType.body_fat_percentage, Decimal("30.4"), "google", unit="")
        assert result == Decimal("30.4")

    def test_samsung_body_fat_not_scaled(self) -> None:
        result = unit_conversion_service.convert(SeriesType.body_fat_percentage, Decimal("18.5"), "samsung", unit="")
        assert result == Decimal("18.5")

    def test_explicit_canonical_unit_overrides_provider_default(self) -> None:
        # An explicit "percent" unit must override Apple's ratio default -> no scaling.
        result = unit_conversion_service.convert(
            SeriesType.body_fat_percentage, Decimal("22.0"), "apple", unit="percent"
        )
        assert result == Decimal("22.0")


class TestUnitConversionPassthrough:
    """Metrics already in canonical units are returned unchanged."""

    def test_heart_rate_passthrough(self) -> None:
        result = unit_conversion_service.convert(SeriesType.heart_rate, Decimal("72"), "apple", unit="")
        assert result == Decimal("72")

    def test_unit_absent_for_unknown_provider_passes_through(self) -> None:
        # No per-provider default for fitbit -> value assumed canonical -> passthrough.
        result = unit_conversion_service.convert(SeriesType.height, Decimal("1.75"), "fitbit", unit="")
        assert result == Decimal("1.75")


class TestUnitConversionUnknownUnit:
    """A present-but-unrecognized unit returns None (caller logs + skips)."""

    def test_unrecognized_unit_returns_none(self) -> None:
        result = unit_conversion_service.convert(SeriesType.height, Decimal("70"), "apple", unit="inches")
        assert result is None

    def test_none_unit_uses_provider_default(self) -> None:
        # unit=None normalizes to absent (not unrecognized) -> provider default applies.
        result = unit_conversion_service.convert(SeriesType.height, Decimal("1.7526"), "apple", unit=None)
        assert str(result) == "175.2600"


def test_module_singleton_is_unit_conversion_service() -> None:
    assert isinstance(unit_conversion_service, UnitConversionService)
