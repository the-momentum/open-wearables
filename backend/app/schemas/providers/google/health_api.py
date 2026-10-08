"""Google Health API metric-mapping schemas.

Declarative mapping of a Google data type to a unified SeriesType. A data type may
support the ``rollUp`` operation (windowed aggregates), the ``list`` operation (raw
data points), or both. Windowed rollUp is currently disabled (see ``DataTypeMetric.use_list``),
so every type is read at native resolution.
"""

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.enums import DataGranularity, SeriesType


class DataPointsPage(BaseModel):
    """One page of a dataPoints, dataPoints:reconcile or dataPoints:rollUp response.

    All three share the envelope and differ only in which list they fill; every field is
    optional because Google omits empty ones (an exhausted window returns ``{}``, and a
    page can carry a token with no points).
    """

    data_points: list[dict[str, Any]] = Field(default_factory=list, alias="dataPoints")
    rollup_data_points: list[dict[str, Any]] = Field(default_factory=list, alias="rollupDataPoints")
    next_page_token: str | None = Field(None, alias="nextPageToken")


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
class DerivedSeriesField:
    """A series computed as ``field - against`` within one value object.

    Google publishes a nightly value and the baseline it should be read against, never the
    difference; providers that do report a deviation report exactly that subtraction.
    """

    series_type: SeriesType
    field: str
    against: str
    scale: Decimal = Decimal(1)


@dataclass(frozen=True)
class RollupSpec:
    """How to read one data type's value from a dataPoints:rollUp response.

    field:          key of the scalar within the ``*RollupValue`` object (e.g. ``countSum``).
    subfield:       second-level key when nested (e.g. hydration's ``amountConsumed`` →
                    ``millilitersSum``); None for the flat common case.
    scale:          unit factor applied to the value (e.g. 0.001 for mm→m).
    max_range_days: rollUp's per-request range cap (14 for heart-rate, else 90).
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
    session_interval: True for SessionTimeInterval types (filter on interval.civil_start_time).
    extra:          additional series emitted from the same value object, if any.
    derived:        series computed from two fields of the same value object, if any.
    """

    field: str
    time: TimeShape
    subfield: str | None = None
    scale: Decimal = Decimal(1)
    is_daily_total: bool = False
    session_interval: bool = False
    extra: tuple[SeriesField, ...] | None = None
    derived: tuple[DerivedSeriesField, ...] | None = None


@dataclass(frozen=True)
class LevelSum:
    """A sum over the per-level list of a ``*RollupValue`` object, keeping only some levels.

    level_key:   key naming each entry's level (e.g. ``activityLevel``).
    value_field: key of each entry's number (e.g. ``activeMinutesSum``).
    levels:      levels included in the sum.
    """

    level_key: str
    value_field: str
    levels: frozenset[str]


@dataclass(frozen=True)
class DailyRollupSpec:
    """How to read one data type's civil-day total from a dataPoints:dailyRollUp response.

    data_type/value_key: the type to request and the union key its value lands under.
    field:               key of the scalar within the ``*RollupValue`` object (e.g. ``kcalSum``),
                         or of the per-level list when ``level_sum`` is set.
    scale:               unit factor applied to the value.
    max_range_days:      dailyRollUp's per-request range cap (14 for total-calories and active-minutes, else 90).
    level_sum:           which levels of the ``field`` list to add up, for per-level types.
    """

    data_type: str
    value_key: str
    field: str
    scale: Decimal = Decimal(1)
    max_range_days: int = 90
    level_sum: LevelSum | None = None


@dataclass(frozen=True)
class DerivedDailyMetric:
    """A civil-day total computed as ``operation(left, right)`` — ``operator.add`` or ``operator.sub``.

    Both operands are fetched independently from dailyRollUp and matched on civil date, so
    the metric owns its inputs and never depends on another metric having run first. A day
    is emitted only when both operands returned a value for it.

    data_source_family scopes both operands to the same sources. Without it they aggregate
    over different source populations and the result is meaningless — subtracting all-source
    active from Fitbit-modelled total-calories went negative on 51 of 82 days.
    """

    name: str
    series_type: SeriesType
    left: DailyRollupSpec
    right: DailyRollupSpec
    operation: Callable[[Decimal, Decimal], Decimal]
    data_source_family: str = "users/me/dataSourceFamilies/google-sources"


@dataclass(frozen=True)
class DailyRollupMetric:
    """A civil-day total read straight from one data type's dailyRollUp.

    data_source_family keeps the total to first-party sources, since points from several
    sources on one civil day are summed and would otherwise count the same minutes twice.
    """

    name: str
    series_type: SeriesType
    spec: DailyRollupSpec
    data_source_family: str = "users/me/dataSourceFamilies/google-sources"


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
        # A rollUp-only type would ingest nothing while rollUp is off (see use_list).
        if self.list_spec is None:
            raise ValueError(f"{self.data_type}: must declare a list spec")

    def use_list(self, granularity: DataGranularity) -> bool:
        """Always the native-resolution op: windowed rollUp is disabled (#1577).

        rollUp window starts do not line up with the timestamps backfill and live sync write,
        so the same reading misses the uniqueness index and inserts a duplicate instead of
        updating. Every registered type declares a list spec, so nothing loses ingestion.
        Re-enable by restoring the granularity check once window starts are floored.
        """
        return True

    def series_types(self) -> frozenset[SeriesType]:
        """Every series this metric can emit — primary, extra bindings and derived ones."""
        extra = (
            sf.series_type
            for spec in (self.rollup_spec, self.list_spec)
            if spec is not None and spec.extra
            for sf in spec.extra
        )
        derived = (df.series_type for df in (self.list_spec.derived if self.list_spec else None) or ())
        return frozenset({self.series_type, *extra, *derived})
