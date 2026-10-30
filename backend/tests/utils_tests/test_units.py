"""Tests for unit conversion between provider units and series units."""

from decimal import Decimal

import pytest

from app.schemas.enums import SeriesType
from app.utils.units import (
    BloodGlucoseUnit,
    EnergyUnit,
    LengthUnit,
    MassUnit,
    SpeedUnit,
    TemperatureUnit,
    Unit,
    UnitConverter,
    VolumeUnit,
    parse_unit,
)


class TestParseUnit:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("km", LengthUnit.km),
            ("m", LengthUnit.m),
            ("meters", LengthUnit.m),
            ("ft", LengthUnit.ft),
            ("lb", MassUnit.lb),
            ("mcg", MassUnit.mcg),
            ("L", VolumeUnit.liter),
            ("mL", VolumeUnit.ml),
            ("fl_oz_us", VolumeUnit.fl_oz_us),
            ("kJ", EnergyUnit.kj),
            ("km/hr", SpeedUnit.km_per_h),
            ("ft/s", SpeedUnit.ft_per_s),
            ("degF", TemperatureUnit.fahrenheit),
            ("°C", TemperatureUnit.celsius),
            ("mg/dL", BloodGlucoseUnit.mg_dl),
            ("mmol<180.15588000005408>/L", BloodGlucoseUnit.mmol_l),
            (" km ", LengthUnit.km),
        ],
    )
    def test_maps_provider_strings(self, raw: str, expected: Unit) -> None:
        assert parse_unit(raw) == expected

    def test_small_calorie_and_food_calorie_differ(self) -> None:
        assert parse_unit("cal") == EnergyUnit.cal
        assert parse_unit("Cal") == EnergyUnit.kcal

    @pytest.mark.parametrize("raw", [None, "", "count/min", "furlong"])
    def test_unknown_or_missing_is_none(self, raw: str | None) -> None:
        assert parse_unit(raw) is None


class TestUnitConverter:
    @pytest.mark.parametrize(
        ("value", "from_unit", "to_unit", "expected"),
        [
            (Decimal("0.021"), LengthUnit.km, LengthUnit.m, Decimal("21")),
            (Decimal("1.75"), LengthUnit.m, LengthUnit.cm, Decimal("175")),
            (Decimal("6"), LengthUnit.ft, LengthUnit.cm, Decimal("182.88")),
            (Decimal("1"), LengthUnit.mi, LengthUnit.m, Decimal("1609.344")),
            (Decimal("150"), MassUnit.lb, MassUnit.kg, Decimal("68.0388555")),
            (Decimal("1"), MassUnit.st, MassUnit.kg, Decimal("6.35029318")),
            (Decimal("0.5"), VolumeUnit.liter, VolumeUnit.ml, Decimal("500")),
            (Decimal("500"), EnergyUnit.cal, EnergyUnit.kcal, Decimal("0.5")),
            (Decimal("36"), SpeedUnit.km_per_h, SpeedUnit.m_per_s, Decimal("10")),
            (Decimal("1"), SpeedUnit.ft_per_s, SpeedUnit.m_per_s, Decimal("0.3048")),
            (Decimal("6.25"), SpeedUnit.mi_per_h, SpeedUnit.m_per_s, Decimal("2.794")),
            (Decimal("98.6"), TemperatureUnit.fahrenheit, TemperatureUnit.celsius, Decimal("37")),
            (Decimal("37"), TemperatureUnit.celsius, TemperatureUnit.fahrenheit, Decimal("98.6")),
            (Decimal("310.15"), TemperatureUnit.kelvin, TemperatureUnit.celsius, Decimal("37")),
            (Decimal("6.1"), BloodGlucoseUnit.mmol_l, BloodGlucoseUnit.mg_dl, Decimal("109.91102")),
        ],
    )
    def test_converts(self, value: Decimal, from_unit: Unit, to_unit: Unit, expected: Decimal) -> None:
        result = UnitConverter.convert(value, from_unit, to_unit)

        assert result is not None
        assert result == pytest.approx(expected, abs=Decimal("0.000001"))

    @pytest.mark.parametrize(
        ("value", "from_unit", "to_unit", "expected"),
        [
            (Decimal("41.84"), EnergyUnit.kj, EnergyUnit.kcal, Decimal("10")),
            (Decimal("418.4"), EnergyUnit.kj, EnergyUnit.kcal, Decimal("100")),
            (Decimal("4184"), EnergyUnit.j, EnergyUnit.kcal, Decimal("1")),
            (Decimal("36"), SpeedUnit.km_per_h, SpeedUnit.m_per_s, Decimal("10")),
        ],
    )
    def test_round_values_stay_exact(self, value: Decimal, from_unit: Unit, to_unit: Unit, expected: Decimal) -> None:
        assert UnitConverter.convert(value, from_unit, to_unit) == expected

    def test_same_unit_is_unchanged(self) -> None:
        assert UnitConverter.length(Decimal("1.234"), LengthUnit.cm, LengthUnit.cm) == Decimal("1.234")

    def test_different_quantities_do_not_convert(self) -> None:
        assert UnitConverter.convert(Decimal(1), LengthUnit.km, MassUnit.kg) is None

    def test_convert_raw_unknown_unit_is_none(self) -> None:
        assert UnitConverter.convert_raw(Decimal(1), "furlong", LengthUnit.m) is None


class TestToSeriesUnit:
    @pytest.mark.parametrize(
        ("series_type", "value", "raw_unit", "expected"),
        [
            (SeriesType.blood_glucose, Decimal("6.1"), "mmol<180.15588000005408>/L", Decimal("109.91102")),
            (SeriesType.blood_glucose, Decimal("110"), "mg/dL", Decimal("110")),
            (SeriesType.distance_walking_running, Decimal("0.021"), "km", Decimal("21")),
            (SeriesType.distance_cycling, Decimal("1"), "mi", Decimal("1609.344")),
            (SeriesType.height, Decimal("175"), "cm", Decimal("175")),
            (SeriesType.height, Decimal("6"), "ft", Decimal("182.88")),
            (SeriesType.weight, Decimal("150"), "lb", Decimal("68.0388555")),
            (SeriesType.body_temperature, Decimal("98.6"), "degF", Decimal("37")),
            (SeriesType.walking_speed, Decimal("3.6"), "km/hr", Decimal("1")),
            (SeriesType.stair_ascent_speed, Decimal("1.17239"), "ft/s", Decimal("0.357344472")),
            (SeriesType.hydration, Decimal("0.25"), "L", Decimal("250")),
            (SeriesType.dietary_energy_consumed, Decimal("1000"), "kJ", Decimal("239.005736")),
            (SeriesType.dietary_sodium, Decimal("0.5"), "g", Decimal("500")),
        ],
    )
    def test_converts_to_series_unit(
        self, series_type: SeriesType, value: Decimal, raw_unit: str, expected: Decimal
    ) -> None:
        result = UnitConverter.to_series_unit(series_type, value, raw_unit)

        assert result is not None
        assert result == pytest.approx(expected, abs=Decimal("0.000001"))

    @pytest.mark.parametrize(
        ("series_type", "raw_unit"),
        [
            (SeriesType.heart_rate, "count/min"),
            (SeriesType.steps, "count"),
            (SeriesType.blood_alcohol_content, "%"),
            (SeriesType.skin_temperature_deviation, "degF"),
            (SeriesType.garmin_skin_temperature, "degF"),
        ],
    )
    def test_series_without_convertible_unit_is_unchanged(self, series_type: SeriesType, raw_unit: str) -> None:
        assert UnitConverter.to_series_unit(series_type, Decimal("72"), raw_unit) == Decimal("72")

    @pytest.mark.parametrize("raw_unit", [None, "", "furlong", "kg"])
    def test_unknown_or_mismatched_unit_is_none(self, raw_unit: str | None) -> None:
        assert UnitConverter.to_series_unit(SeriesType.distance_walking_running, Decimal("1"), raw_unit) is None
