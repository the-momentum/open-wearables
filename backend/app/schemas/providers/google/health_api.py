"""Google Health API metric-mapping schemas.

Declarative mapping of a Google data type to a unified SeriesType. A data type may
support the ``rollUp`` operation (windowed aggregates), the ``list`` operation (raw
data points), or both; the handler picks the operation per the configured granularity.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from app.schemas.enums import DataGranularity, SeriesType


class TimeShape(Enum):
    """Where a list data point carries its timestamp, by Google record type.

    INTERVAL — ``interval.startTime`` (Interval & Session types)
    SAMPLE   — ``sampleTime.physicalTime`` (Sample types)
    DATE     — ``date`` {year, month, day} (Daily types)
    """

    INTERVAL = "interval"
    SAMPLE = "sample"
    DATE = "date"


@dataclass(frozen=True)
class SeriesField:
    """An additional (series, value) extracted from the same value object.

    Lets one data type emit several series (e.g. an HRV sample yields both RMSSD and SDNN)
    from a single fetch, beyond the spec's primary field.
    """

    series_type: SeriesType
    field: str
    subfield: str | None = None
    scale: Decimal = Decimal(1)


@dataclass(frozen=True)
class RollupSpec:
    """How to read one data type's value from a dataPoints:rollUp response.

    field:          key of the scalar within the ``*RollupValue`` object (e.g. ``countSum``).
    subfield:       second-level key when nested (e.g. hydration's ``amountConsumed`` →
                    ``millilitersSum``); None for the flat common case.
    scale:          unit factor applied to the value (e.g. 0.001 for mm→m).
    max_range_days: rollUp's per-request range cap (14 for heart-rate/total-calories, else 90).
    extra:          additional series emitted from the same value object, if any.
    """

    field: str
    subfield: str | None = None
    scale: Decimal = Decimal(1)
    max_range_days: int = 90
    extra: tuple[SeriesField, ...] | None = None


@dataclass(frozen=True)
class ListSpec:
    """How to read one data type's value + timestamp from a dataPoints list response.

    field/subfield: key (and optional nested key) of the scalar within a data point.
    time:           where the data point carries its timestamp (record-type dependent).
    scale:          unit factor applied to the value.
    is_daily_total: True for once-per-day summaries (Daily types), False for raw samples.
    extra:          additional series emitted from the same value object, if any.
    """

    field: str
    time: TimeShape
    subfield: str | None = None
    scale: Decimal = Decimal(1)
    is_daily_total: bool = False
    extra: tuple[SeriesField, ...] | None = None


@dataclass(frozen=True)
class DataTypeMetric:
    """One Google data type mapped to a unified series, with its supported operations.

    value_key: the DataPoint/RollupDataPoint union field this type's payload lives under
               (camelCase, e.g. ``steps``, ``heartRate``, ``dailyRestingHeartRate``). Shared
               by both operations — rollUp and list both nest the value under it.
    """

    data_type: str
    series_type: SeriesType
    value_key: str
    rollup_spec: RollupSpec | None = None
    list_spec: ListSpec | None = None

    def __post_init__(self) -> None:
        if self.rollup_spec is None and self.list_spec is None:
            raise ValueError(f"{self.data_type}: must declare a rollup and/or list spec")

    def use_list(self, granularity: DataGranularity) -> bool:
        """Pick the operation: forced types use their only op; dual types use list only for RAW."""
        if self.rollup_spec is None:
            return True
        if self.list_spec is None:
            return False
        return granularity == DataGranularity.RAW

    def series_types(self) -> frozenset[SeriesType]:
        """Every series this metric can emit — primary plus any extra bindings."""
        extra = (
            sf.series_type
            for spec in (self.rollup_spec, self.list_spec)
            if spec is not None and spec.extra
            for sf in spec.extra
        )
        return frozenset({self.series_type, *extra})
