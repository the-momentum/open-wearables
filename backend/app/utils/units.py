"""Unit conversion for values stored under a fixed series unit.

Each physical quantity has a StrEnum of the units we can convert between. Where
a unit is also a series unit, its value is the same string used in
SERIES_TYPE_DEFINITIONS (e.g. LengthUnit.m == "meters"), so the series unit maps
straight onto a member. Raw unit strings from providers (Apple's "km", "degF",
"mmol<180.15588000005408>/L") are mapped through parse_unit.
"""

from decimal import Decimal
from enum import StrEnum

from app.schemas.enums.series_types import SeriesType, get_series_type_unit


class LengthUnit(StrEnum):
    mm = "mm"
    cm = "cm"
    m = "meters"
    km = "km"
    inch = "in"
    ft = "ft"
    yd = "yd"
    mi = "mi"


class MassUnit(StrEnum):
    mcg = "mcg"
    mg = "mg"
    g = "g"
    kg = "kg"
    oz = "oz"
    lb = "lb"
    st = "st"


class VolumeUnit(StrEnum):
    ml = "mL"
    liter = "liters"
    fl_oz_us = "fl_oz_us"
    fl_oz_imp = "fl_oz_imp"
    cup_us = "cup_us"


class EnergyUnit(StrEnum):
    j = "j"
    cal = "cal"
    kj = "kj"
    kcal = "kcal"


class SpeedUnit(StrEnum):
    m_per_s = "m_per_s"
    km_per_h = "km_per_h"
    mi_per_h = "mi_per_h"
    ft_per_s = "ft_per_s"


class TemperatureUnit(StrEnum):
    celsius = "celsius"
    fahrenheit = "fahrenheit"
    kelvin = "kelvin"


class BloodGlucoseUnit(StrEnum):
    mg_dl = "mg_dl"
    mmol_l = "mmol_l"


type Unit = LengthUnit | MassUnit | VolumeUnit | EnergyUnit | SpeedUnit | TemperatureUnit | BloodGlucoseUnit

# Factors to the first unit of each table: value_in_base = value * factor[unit].
# Energy and speed use J and m/h as base so every factor is exact: with a kcal or
# m/s base, kJ and km/h factors would be repeating decimals (41.84 kJ -> 9.999... kcal).
_LENGTH_TO_M: dict[LengthUnit, Decimal] = {
    LengthUnit.m: Decimal(1),
    LengthUnit.mm: Decimal("0.001"),
    LengthUnit.cm: Decimal("0.01"),
    LengthUnit.km: Decimal(1000),
    LengthUnit.inch: Decimal("0.0254"),
    LengthUnit.ft: Decimal("0.3048"),
    LengthUnit.yd: Decimal("0.9144"),
    LengthUnit.mi: Decimal("1609.344"),
}

_MASS_TO_G: dict[MassUnit, Decimal] = {
    MassUnit.g: Decimal(1),
    MassUnit.mcg: Decimal("0.000001"),
    MassUnit.mg: Decimal("0.001"),
    MassUnit.kg: Decimal(1000),
    MassUnit.oz: Decimal("28.349523125"),
    MassUnit.lb: Decimal("453.59237"),
    MassUnit.st: Decimal("6350.29318"),
}

_VOLUME_TO_ML: dict[VolumeUnit, Decimal] = {
    VolumeUnit.ml: Decimal(1),
    VolumeUnit.liter: Decimal(1000),
    VolumeUnit.fl_oz_us: Decimal("29.5735295625"),
    VolumeUnit.fl_oz_imp: Decimal("28.4130625"),
    VolumeUnit.cup_us: Decimal("236.5882365"),
}

_ENERGY_TO_J: dict[EnergyUnit, Decimal] = {
    EnergyUnit.j: Decimal(1),
    EnergyUnit.cal: Decimal("4.184"),
    EnergyUnit.kj: Decimal(1000),
    EnergyUnit.kcal: Decimal(4184),
}

_SPEED_TO_M_PER_H: dict[SpeedUnit, Decimal] = {
    SpeedUnit.m_per_s: Decimal(3600),
    SpeedUnit.km_per_h: Decimal(1000),
    SpeedUnit.mi_per_h: Decimal("1609.344"),
    SpeedUnit.ft_per_s: Decimal("1097.28"),
}

# Health Connect's own mg/dL converter uses exactly 18.0, so values written to HC
# in mg/dL round-trip with a ~0.1% offset under this factor. Apple's mmol unit
# encodes glucose's molar mass (180.15588 g/mol, i.e. 18.015588), ~0.015% off.
_BLOOD_GLUCOSE_TO_MG_DL: dict[BloodGlucoseUnit, Decimal] = {
    BloodGlucoseUnit.mg_dl: Decimal(1),
    BloodGlucoseUnit.mmol_l: Decimal("18.0182"),
}

_UNIT_ENUMS: tuple[type[Unit], ...] = (
    LengthUnit,
    MassUnit,
    VolumeUnit,
    EnergyUnit,
    SpeedUnit,
    TemperatureUnit,
    BloodGlucoseUnit,
)

# Raw unit strings as providers write them. Case matters: "cal" is a small calorie
# (1/1000 kcal), "Cal" is the food Calorie (= kcal).
_UNIT_ALIASES: dict[str, Unit] = {
    "m": LengthUnit.m,
    "meter": LengthUnit.m,
    "mile": LengthUnit.mi,
    "lbs": MassUnit.lb,
    "ml": VolumeUnit.ml,
    "L": VolumeUnit.liter,
    "l": VolumeUnit.liter,
    "liter": VolumeUnit.liter,
    "litre": VolumeUnit.liter,
    "litres": VolumeUnit.liter,
    "J": EnergyUnit.j,
    "kJ": EnergyUnit.kj,
    "Cal": EnergyUnit.kcal,
    "m/s": SpeedUnit.m_per_s,
    "km/hr": SpeedUnit.km_per_h,
    "km/h": SpeedUnit.km_per_h,
    "mi/hr": SpeedUnit.mi_per_h,
    "mph": SpeedUnit.mi_per_h,
    "ft/s": SpeedUnit.ft_per_s,
    "degC": TemperatureUnit.celsius,
    "°C": TemperatureUnit.celsius,
    "degF": TemperatureUnit.fahrenheit,
    "°F": TemperatureUnit.fahrenheit,
    "K": TemperatureUnit.kelvin,
    "mg/dL": BloodGlucoseUnit.mg_dl,
}

_UNITS_BY_NAME: dict[str, Unit] = {unit.value: unit for enum in _UNIT_ENUMS for unit in enum} | _UNIT_ALIASES

# Series whose unit names a quantity we can convert to. blood_alcohol_content is
# also stored in mg_dl, but glucose's molar factor doesn't apply to it; the
# deviation series hold temperature differences, which the affine °F formula breaks.
_NON_CONVERTIBLE_SERIES = frozenset(
    {
        SeriesType.blood_alcohol_content,
        SeriesType.skin_temperature_deviation,
        SeriesType.skin_temperature_trend_deviation,
        SeriesType.garmin_skin_temperature,
    }
)

_SERIES_UNITS: dict[SeriesType, Unit] = {
    series_type: unit
    for series_type in SeriesType
    if series_type not in _NON_CONVERTIBLE_SERIES
    if (unit := _UNITS_BY_NAME.get(get_series_type_unit(series_type))) is not None
}


def parse_unit(raw_unit: str | None) -> Unit | None:
    """Map a provider's unit string to a Unit; None if missing or unknown."""
    if not raw_unit:
        return None
    raw_unit = raw_unit.strip()
    # Apple encodes the molar mass in the unit, e.g. "mmol<180.15588000005408>/L".
    if raw_unit.lower().startswith("mmol"):
        return BloodGlucoseUnit.mmol_l
    return _UNITS_BY_NAME.get(raw_unit)


def _scale[UnitT: Unit](value: Decimal, from_unit: UnitT, to_unit: UnitT, factors: dict[UnitT, Decimal]) -> Decimal:
    if from_unit == to_unit:
        return value
    return value * factors[from_unit] / factors[to_unit]


class UnitConverter:
    """Convert values between units of one physical quantity."""

    @staticmethod
    def length(value: Decimal, from_unit: LengthUnit, to_unit: LengthUnit) -> Decimal:
        return _scale(value, from_unit, to_unit, _LENGTH_TO_M)

    @staticmethod
    def mass(value: Decimal, from_unit: MassUnit, to_unit: MassUnit) -> Decimal:
        return _scale(value, from_unit, to_unit, _MASS_TO_G)

    @staticmethod
    def volume(value: Decimal, from_unit: VolumeUnit, to_unit: VolumeUnit) -> Decimal:
        return _scale(value, from_unit, to_unit, _VOLUME_TO_ML)

    @staticmethod
    def energy(value: Decimal, from_unit: EnergyUnit, to_unit: EnergyUnit) -> Decimal:
        return _scale(value, from_unit, to_unit, _ENERGY_TO_J)

    @staticmethod
    def speed(value: Decimal, from_unit: SpeedUnit, to_unit: SpeedUnit) -> Decimal:
        return _scale(value, from_unit, to_unit, _SPEED_TO_M_PER_H)

    @staticmethod
    def blood_glucose(value: Decimal, from_unit: BloodGlucoseUnit, to_unit: BloodGlucoseUnit) -> Decimal:
        return _scale(value, from_unit, to_unit, _BLOOD_GLUCOSE_TO_MG_DL)

    @staticmethod
    def temperature(value: Decimal, from_unit: TemperatureUnit, to_unit: TemperatureUnit) -> Decimal:
        # Affine, so it goes through celsius rather than a factor table.
        if from_unit == to_unit:
            return value
        match from_unit:
            case TemperatureUnit.fahrenheit:
                celsius = (value - 32) * 5 / 9
            case TemperatureUnit.kelvin:
                celsius = value - Decimal("273.15")
            case TemperatureUnit.celsius:
                celsius = value
        match to_unit:
            case TemperatureUnit.fahrenheit:
                return celsius * 9 / 5 + 32
            case TemperatureUnit.kelvin:
                return celsius + Decimal("273.15")
            case TemperatureUnit.celsius:
                return celsius

    @classmethod
    def convert(cls, value: Decimal, from_unit: Unit, to_unit: Unit) -> Decimal | None:
        """Convert between any two units; None if they measure different quantities."""
        match from_unit, to_unit:
            case LengthUnit(), LengthUnit():
                return cls.length(value, from_unit, to_unit)
            case MassUnit(), MassUnit():
                return cls.mass(value, from_unit, to_unit)
            case VolumeUnit(), VolumeUnit():
                return cls.volume(value, from_unit, to_unit)
            case EnergyUnit(), EnergyUnit():
                return cls.energy(value, from_unit, to_unit)
            case SpeedUnit(), SpeedUnit():
                return cls.speed(value, from_unit, to_unit)
            case TemperatureUnit(), TemperatureUnit():
                return cls.temperature(value, from_unit, to_unit)
            case BloodGlucoseUnit(), BloodGlucoseUnit():
                return cls.blood_glucose(value, from_unit, to_unit)
            case _:
                return None

    @classmethod
    def convert_raw(cls, value: Decimal, raw_unit: str | None, to_unit: Unit) -> Decimal | None:
        """Convert from a provider's unit string; None if it is unknown or measures something else."""
        from_unit = parse_unit(raw_unit)
        return cls.convert(value, from_unit, to_unit) if from_unit is not None else None

    @classmethod
    def to_series_unit(cls, series_type: SeriesType, value: Decimal, raw_unit: str | None) -> Decimal | None:
        """Convert a value reported in raw_unit to the unit its series is stored in.

        Series stored in a unit with no conversion (bpm, count, percent, ...) are
        returned unchanged. None means the series has a convertible unit but
        raw_unit is missing, unknown or measures something else.
        """
        series_unit = _SERIES_UNITS.get(series_type)
        if series_unit is None:
            return value
        return cls.convert_raw(value, raw_unit, series_unit)
