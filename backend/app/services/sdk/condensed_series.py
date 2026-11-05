"""HealthKit condensed series: older workout samples HealthKit merged into one sample after OW stored them (#1983).

HealthKit condenses the samples of first-party workouts a few months old into quantity series and deletes the
originals. The SDK uploads a series as a new sample, which would count the workout twice next to the originals OW
already holds, so a series is dropped when its window covers stored samples of its type from the same Apple device.
A series OW holds no originals for (a workout condensed before its first export) is kept.
"""

from collections import Counter
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.constants.devices_map import is_apple_own_source
from app.database import DbSession
from app.models import SeriesSample
from app.repositories.data_point_series_repository import DataPointSeriesRepository, StoredWindow
from app.schemas.enums import AggregationMethod, SeriesType, get_series_type_id
from app.schemas.enums.aggregation_method import get_aggregation_method
from app.schemas.model_crud.activities import TimeSeriesSampleCreate
from app.utils.dates import as_utc
from app.utils.structured_logging import get_logger

logger = get_logger(__name__)

# The types Apple documents as condensed; a sample the SDK sends a count for is checked whatever its type
CONDENSED_TYPES = frozenset(
    {
        SeriesType.heart_rate,
        SeriesType.active_energy,
        SeriesType.basal_energy,
        SeriesType.distance_walking_running,
        SeriesType.distance_cycling,
    }
)
# Apple condenses workouts a few months old, so a younger sample is never checked, whatever its count
MIN_CONDENSED_AGE = timedelta(days=30)
# Without a count, a series covers at least this many stored samples: one alone can be an overlapping reading
MIN_COVERED = 2
# Without a count, a cumulative series is the sum of the stored samples it covers, within this share of its value
SUM_TOLERANCE = Decimal("0.01")

_series_repo = DataPointSeriesRepository(SeriesSample)


def is_candidate(sample: TimeSeriesSampleCreate, count: int | None, now: datetime) -> bool:
    """Whether a sample may be a condensed series: an Apple device's sample with a window, older than
    MIN_CONDENSED_AGE, with a count above 1 or, without a count, of a type HealthKit condenses."""
    if not sample.window_seconds or not is_apple_own_source(sample.source_app_id):
        return False
    if as_utc(sample.recorded_at) >= now - MIN_CONDENSED_AGE:
        return False
    if count is not None:
        return count > 1
    return sample.series_type in CONDENSED_TYPES


def is_condensed(sample: TimeSeriesSampleCreate, count: int | None, stored: int, total: Decimal) -> bool:
    """Whether a candidate repeats samples OW holds: `stored` samples summing to `total` inside its window."""
    if count is not None:
        return stored >= 1
    if stored < MIN_COVERED:
        return False
    if get_aggregation_method(sample.series_type) is AggregationMethod.SUM:
        value = Decimal(str(sample.value))
        return abs(value - total) <= abs(value) * SUM_TOLERANCE
    return True


def drop_condensed_series[SampleT: TimeSeriesSampleCreate](
    db_session: DbSession,
    samples: list[SampleT],
    counts: Mapping[str, int],
    now: datetime | None = None,
) -> list[SampleT]:
    """The samples without the condensed series whose originals OW already holds.

    The samples are one user's (one SDK upload). `counts` maps a record id to the count the SDK sent for it;
    a sample without one is judged by its window.
    """
    now = now or datetime.now(timezone.utc)
    candidates = [sample for sample in samples if is_candidate(sample, _count(sample, counts), now)]
    if not candidates:
        return samples
    coverage = _series_repo.stored_in_windows(
        db_session,
        [_window(sample) for sample in candidates],
    )
    dropped = [
        sample
        for sample, (covered, total) in zip(candidates, coverage, strict=True)
        if is_condensed(sample, _count(sample, counts), covered, total)
    ]
    if not dropped:
        return samples
    logger.info(
        "Dropped HealthKit condensed series over stored samples",
        action="sdk_condensed_series_dropped",
        user_id=str(dropped[0].user_id),
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
        user_id=sample.user_id,
        source_app_id=sample.source_app_id,
        series_type_definition_id=get_series_type_id(sample.series_type),
        start=start,
        end=start + timedelta(seconds=sample.window_seconds or 0),
        external_id=sample.external_id,
    )
