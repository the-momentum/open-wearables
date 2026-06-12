"""Centralized unit conversion service.

Single source of truth for converting incoming provider values into the canonical
units defined by ``SERIES_TYPE_DEFINITIONS`` (see ``app/schemas/enums/series_types.py``).

Background: providers report metrics in heterogeneous units, and incoming records
frequently omit the unit string entirely (``MetricRecord.unit`` is ``str | None`` and is
empty in practice). Conversion therefore cannot rely solely on a ``(series_type, unit)``
lookup — when the unit is absent we fall back to a per-provider *default source unit*.
This keeps the provider-specific knowledge (e.g. Apple sends body fat as a 0..1 ratio
while Health Connect sends percent) as data in one place rather than scattered ``if``
branches across importers.

Conversions are ``Decimal``-preserving: each converter multiplies by an integer literal so
the resulting ``Decimal`` scale matches the previous hardcoded behavior exactly.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Callable

from app.schemas.enums import SeriesType, get_series_type_unit

_UNIT_ABSENT = "__absent__"


def _times_100(value: Decimal) -> Decimal:
    # Integer literal 100 preserves Decimal scale: Decimal("1.7526") * 100 == Decimal("175.2600").
    return value * 100


# Per-provider default source unit (used when the unit string is absent)
#
# Encodes the knowledge previously hardcoded in import_service._build_statistic_bundles:
#   - height is reported in meters by every SDK provider (apple/google/samsung).
#   - body_fat_percentage is a 0..1 ratio on Apple, but already a percent on Health Connect
#     (google/samsung), so only Apple needs scaling.
_PROVIDER_DEFAULT_SOURCE_UNIT: dict[str, dict[SeriesType, str]] = {
    "apple": {SeriesType.height: "meters", SeriesType.body_fat_percentage: "ratio"},
    "google": {SeriesType.height: "meters", SeriesType.body_fat_percentage: "percent"},
    "samsung": {SeriesType.height: "meters", SeriesType.body_fat_percentage: "percent"},
}


# Conversion registry: (series_type, source_unit) -> converter
# Only NON-canonical source units need an entry. Canonical-unit sources and metrics with no
# registered conversion fall through to passthrough (value returned unchanged).
_CONVERSIONS: dict[tuple[SeriesType, str], Callable[[Decimal], Decimal]] = {
    (SeriesType.height, "meters"): _times_100,
    (SeriesType.body_fat_percentage, "ratio"): _times_100,
}


class UnitConversionService:
    """Convert incoming provider values to the canonical unit for their series type."""

    @staticmethod
    def _normalize_unit(unit: str | None) -> str:
        if unit is None:
            return _UNIT_ABSENT

        token = unit.strip()

        return token if token else _UNIT_ABSENT

    def _resolve_source_unit(self, series_type: SeriesType, provider: str, unit_token: str) -> str:
        """Resolve the effective source unit.

        When the unit is supplied, use it verbatim. When absent, fall back to the per-provider
        default; if there is no default for this provider/metric, assume the value is already in
        the canonical unit (passthrough).
        """
        if unit_token != _UNIT_ABSENT:
            return unit_token

        return _PROVIDER_DEFAULT_SOURCE_UNIT.get(provider, {}).get(series_type, get_series_type_unit(series_type))

    def convert(
        self,
        series_type: SeriesType,
        value: Decimal,
        provider: str,
        unit: str | None = None,
    ) -> Decimal | None:
        """Convert ``value`` to the canonical unit for ``series_type``.

        Returns the converted ``Decimal``, or ``None`` when the incoming unit is present but
        unrecognized/unexpected for this metric — signalling the caller to log and skip the
        sample rather than store a wrong-magnitude value.
        """

        canonical = get_series_type_unit(series_type)
        unit_token = self._normalize_unit(unit)
        source_unit = self._resolve_source_unit(series_type, provider, unit_token)

        # If source is already canonical (heart_rate, steps, percent body_fat, ...) -> no change.
        if source_unit == canonical:
            return value

        converter = _CONVERSIONS.get((series_type, source_unit))
        if converter is not None:
            return converter(value)

        # Present but unrecognized source unit for this metric -> caller logs + skips.
        return None


unit_conversion_service = UnitConversionService()
