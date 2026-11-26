"""HealthKit condensed series (#1983).

HealthKit merges the samples of first-party workouts a few months old into one series sample and deletes the
originals. The SDK uploads it as a new sample, dropped when OW holds the originals: they would count twice.
A series kept over only part of its originals still overwrites the one stored at its start (same upsert key).
"""

from collections import Counter
from collections.abc import Mapping
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID

from app.constants.devices_map import is_apple_own_source
from app.database import DbSession
from app.integrations.rollup_queue import mark_dirty_days
from app.models import SeriesSample
from app.repositories.data_point_series_repository import Coverage, DataPointSeriesRepository, StoredWindow
from app.schemas.enums import AggregationMethod, SeriesType, get_series_type_from_id, get_series_type_id
from app.schemas.enums.aggregation_method import get_aggregation_method
from app.schemas.model_crud.activities import TimeSeriesSampleCreate
from app.services.timeseries_service import timeseries_service
from app.utils.dates import as_utc, local_date
from app.utils.structured_logging import get_logger

logger = get_logger(__name__)

# Types Apple documents as condensed; with a count from the SDK, any type is checked
CONDENSED_TYPES = frozenset(
    {
        SeriesType.heart_rate,
        SeriesType.active_energy,
        SeriesType.basal_energy,
        SeriesType.distance_walking_running,
        SeriesType.distance_cycling,
    }
)
# Apple condenses workouts a few months old; 30 days leaves a margin
MIN_CONDENSED_AGE = timedelta(days=30)
# Without a count, one stored sample can be an overlapping reading, so a series must cover this many
_MIN_COVERED = 2
# A cumulative series must equal the sum of the samples it covers, within this share of its value
_SUM_TOLERANCE = Decimal("0.01")
# Above this, what a stored series has over the samples it covers is the original it replaced; less is rounding
_REPLACED_MIN = Decimal("0.001")
# Stored series checked per lookup by the repair
_REPAIR_CHUNK = 2000

_series = DataPointSeriesRepository(SeriesSample)

Repair = Literal["restored", "deleted", "kept"]


def is_candidate(sample: TimeSeriesSampleCreate, count: int | None, now: datetime) -> bool:
    """Whether a sample may be a condensed series, so worth a lookup."""
    if not sample.window_seconds or not is_apple_own_source(sample.source_app_id):
        return False
    # Without an id the lookup can't leave out the sample's own stored row, so a re-send would cover itself
    if not sample.external_id:
        return False
    if as_utc(sample.recorded_at) >= now - MIN_CONDENSED_AGE:
        return False
    if count is not None:
        return count > 1
    return sample.series_type in CONDENSED_TYPES


def is_condensed(sample: TimeSeriesSampleCreate, count: int | None, coverage: Coverage) -> bool:
    """Whether a candidate repeats the stored samples its window covers."""
    if get_aggregation_method(sample.series_type) is AggregationMethod.SUM:
        # The sum also catches a series condensed again over one OW kept, which covers only that one
        enough = coverage.covered >= (1 if count is not None else _MIN_COVERED)
        return enough and _within_sum(Decimal(str(sample.value)), coverage.total)
    # Without a sum to check, a counted series must cover all its readings: one alone may be all OW has of them
    return coverage.covered >= (count if count is not None else _MIN_COVERED)


def _within_sum(value: Decimal, total: Decimal) -> bool:
    return abs(value - total) <= abs(value) * _SUM_TOLERANCE


def repair_action(series_type: SeriesType, value: Decimal, coverage: Coverage) -> tuple[Repair, Decimal | None] | None:
    """The repair for a stored series, and the value to restore when it replaced an original; None for a row that
    covers too few samples to be one."""
    if coverage.covered < _MIN_COVERED:
        return None
    if get_aggregation_method(series_type) is not AggregationMethod.SUM:
        # Over other series only, it may be all OW has of the span: overlapping series would delete each other
        if coverage.instants < _MIN_COVERED:
            return "kept", None
        return "deleted", None  # the reading it replaced can't be recovered
    replaced = value - coverage.total
    # More than twice its largest covered sample can't be one replaced original
    if replaced > 2 * coverage.largest or (replaced < 0 and not _within_sum(value, coverage.total)):
        return "kept", None
    return ("restored", replaced) if replaced > _REPLACED_MIN else ("deleted", None)


def drop_condensed_series[SampleT: TimeSeriesSampleCreate](
    db_session: DbSession, samples: list[SampleT], counts: Mapping[str, int]
) -> list[SampleT]:
    """The samples (one user's upload) without the condensed series whose originals OW holds.

    counts maps a record id to the count the SDK sent for it.
    """
    now = datetime.now(timezone.utc)
    counted = [(sample, _count(sample, counts)) for sample in samples]
    candidates = [(sample, count) for sample, count in counted if is_candidate(sample, count, now)]
    if not candidates:
        return samples
    user_id = candidates[0][0].user_id
    coverages = timeseries_service.stored_in_windows(db_session, user_id, [_window(sample) for sample, _ in candidates])
    dropped = [
        sample
        for (sample, count), coverage in zip(candidates, coverages, strict=True)
        if is_condensed(sample, count, coverage)
    ]
    if not dropped:
        return samples
    logger.info(
        "Dropped HealthKit condensed series over stored samples",
        action="sdk_condensed_series_dropped",
        user_id=str(user_id),
        checked=len(candidates),
        by_type=dict(Counter(sample.series_type.value for sample in dropped)),
    )
    dropped_ids = {sample.id for sample in dropped}
    return [sample for sample in samples if sample.id not in dropped_ids]


def _count(sample: TimeSeriesSampleCreate, counts: Mapping[str, int]) -> int | None:
    return counts.get(sample.external_id) if sample.external_id else None


def _window(sample: TimeSeriesSampleCreate) -> StoredWindow:
    start = as_utc(sample.recorded_at)
    return StoredWindow(
        source_app_id=sample.source_app_id,
        series_type_definition_id=get_series_type_id(sample.series_type),
        start=start,
        end=start + timedelta(seconds=sample.window_seconds or 0),
        external_id=sample.external_id,
    )


def repair_source(
    db_session: DbSession, source_id: UUID, user_id: UUID, app_id: str, before: datetime, *, dry_run: bool = False
) -> Counter[tuple[str, Repair]]:
    """Repair the series a data source stored inside its user's Apple workouts started before ``before`` and queue
    the changed days for the rollup; returns the rows by type and action. Writes nothing on a dry run; the caller
    commits.

    A restored original gets no window and no external id: a later run skips it, and the series sent again counts
    it as covered and is dropped at ingest. data_type_coverage is not narrowed: a deleted row starts within one
    window of the 2+ samples it covers, so the span is at most one window early.
    """
    by_type: Counter[tuple[str, Repair]] = Counter()
    restored: list[tuple[UUID, Decimal]] = []
    deleted: list[UUID] = []
    days: set[date] = set()
    type_ids = {get_series_type_id(series_type) for series_type in CONDENSED_TYPES}
    rows = _series.windowed_in_apple_workouts(db_session, source_id, user_id, type_ids, before)
    for start in range(0, len(rows), _REPAIR_CHUNK):
        chunk = rows[start : start + _REPAIR_CHUNK]
        windows = [
            StoredWindow(
                source_app_id=app_id,
                series_type_definition_id=row.series_type_definition_id,
                start=row.recorded_at,
                end=row.recorded_at + timedelta(seconds=row.window_seconds),
                external_id=row.external_id,
            )
            for row in chunk
        ]
        for row, coverage in zip(
            chunk, timeseries_service.stored_in_windows(db_session, user_id, windows), strict=True
        ):
            series_type = get_series_type_from_id(row.series_type_definition_id)
            if (action := repair_action(series_type, row.value, coverage)) is None:
                continue
            repair, value = action
            by_type[(series_type.value, repair)] += 1
            if repair == "kept":
                continue
            if value is not None:
                restored.append((row.id, value))
            else:
                deleted.append(row.id)
            days.add(local_date(row.recorded_at, row.zone_offset))
    if days and not dry_run:
        _series.restore_replaced(db_session, restored)
        _series.delete_ids(db_session, deleted)
        mark_dirty_days(db_session, [(source_id, day) for day in days])
    return by_type
