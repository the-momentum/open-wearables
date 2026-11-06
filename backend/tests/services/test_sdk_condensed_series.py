"""Which SDK samples may be HealthKit condensed series, and which of them repeat samples OW holds."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.repositories.data_point_series_repository import Coverage
from app.schemas.enums import SeriesType
from app.schemas.model_crud.activities import TimeSeriesSampleCreate
from app.services.sdk.condensed_series import is_candidate, is_condensed, repair_action
from tests.fixtures.healthkit_records import APPLE_WATCH_APP_ID

NOW = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)


def _sample(
    series_type: SeriesType = SeriesType.active_energy,
    *,
    days_ago: int = 120,
    window: int | None = 600,
    app_id: str | None = APPLE_WATCH_APP_ID,
    value: str = "15",
    external_id: str | None = "SERIES",
) -> TimeSeriesSampleCreate:
    return TimeSeriesSampleCreate(
        id=uuid4(),
        external_id=external_id,
        user_id=uuid4(),
        source_app_id=app_id,
        recorded_at=NOW - timedelta(days=days_ago),
        window_seconds=window,
        value=Decimal(value),
        series_type=series_type,
    )


def _coverage(covered: int, total: str, largest: str | None = None, *, instants: int | None = None) -> Coverage:
    """Every covered sample an instant unless told otherwise; the largest is the total by default."""
    return Coverage(
        covered,
        covered if instants is None else instants,
        Decimal(total),
        Decimal(total if largest is None else largest),
    )


class TestIsCandidate:
    def test_an_old_windowed_apple_sample_is_one(self) -> None:
        assert is_candidate(_sample(), None, NOW)

    @pytest.mark.parametrize("count", [None, 4])
    @pytest.mark.parametrize(
        "sample",
        [
            _sample(window=None),
            _sample(app_id="com.ouraring.oura"),
            _sample(app_id=None),
            _sample(days_ago=29),
            _sample(external_id=None),
        ],
        ids=["no window", "third-party app", "no app", "recent", "no record id"],
    )
    def test_no_other_sample_is_whatever_the_count(self, sample: TimeSeriesSampleCreate, count: int | None) -> None:
        assert not is_candidate(sample, count, NOW)

    def test_without_a_count_only_a_condensed_type_is(self) -> None:
        assert not is_candidate(_sample(SeriesType.steps), None, NOW)

    def test_a_count_decides_whatever_the_type(self) -> None:
        assert is_candidate(_sample(SeriesType.steps), 4, NOW)
        assert not is_candidate(_sample(), 1, NOW)

    def test_a_naive_recorded_at_reads_as_utc(self) -> None:
        sample = _sample()
        naive = sample.model_copy(update={"recorded_at": sample.recorded_at.replace(tzinfo=None)})
        assert is_candidate(naive, None, NOW)


class TestIsCondensed:
    def test_with_a_count_a_heart_rate_series_must_cover_all_its_readings(self) -> None:
        heart_rate = _sample(SeriesType.heart_rate, value="148.3")
        assert not is_condensed(heart_rate, 10, _coverage(1, "140"))  # one alone may be all OW has of them
        assert is_condensed(heart_rate, 10, _coverage(10, "1400"))
        assert is_condensed(heart_rate, 4, _coverage(4, "560"))
        assert not is_condensed(heart_rate, 4, _coverage(0, "0"))

    def test_with_a_count_a_cumulative_series_must_match_what_it_covers(self) -> None:
        assert not is_condensed(_sample(value="15"), 10, _coverage(1, "1.5"))  # part of its originals
        assert is_condensed(_sample(value="15"), 10, _coverage(10, "15"))
        # condensed again with a new id over the series OW kept
        assert is_condensed(_sample(value="15"), 3, _coverage(1, "15", instants=0))

    def test_a_cumulative_sample_is_the_sum_of_what_it_covers(self) -> None:
        assert is_condensed(_sample(value="15"), None, _coverage(10, "15"))
        assert is_condensed(_sample(value="15"), None, _coverage(10, "14.9"))  # within 1%
        assert not is_condensed(_sample(value="15"), None, _coverage(10, "14.8"))
        assert not is_condensed(_sample(value="15"), None, _coverage(1, "15"))  # one overlapping reading

    def test_a_heart_rate_sample_only_has_to_cover_stored_readings(self) -> None:
        assert is_condensed(_sample(SeriesType.heart_rate, value="148.3"), None, _coverage(2, "290"))
        assert not is_condensed(_sample(SeriesType.heart_rate, value="148.3"), None, _coverage(1, "140"))

    def test_a_float_value_is_compared_as_a_decimal(self) -> None:
        assert is_condensed(_sample().model_copy(update={"value": 15.0}), None, _coverage(10, "15"))


class TestRepairAction:
    @pytest.mark.parametrize(
        ("series_type", "value", "total", "largest", "expected"),
        [
            (SeriesType.active_energy, "15", "13.5", "1.5", ("restored", Decimal("1.5"))),
            (SeriesType.active_energy, "13.5005", "13.5", "1.5", ("deleted", None)),
            (SeriesType.active_energy, "13.4", "13.5", "1.5", ("deleted", None)),
            (SeriesType.active_energy, "12.4", "13.5", "1.5", ("kept", None)),
            (SeriesType.active_energy, "40", "13.5", "1.5", ("kept", None)),
            (SeriesType.heart_rate, "144.5", "1000", "140", ("deleted", None)),
        ],
    )
    def test_decides_by_what_the_series_has_over_the_sum(
        self, series_type: SeriesType, value: str, total: str, largest: str, expected: tuple[str, Decimal | None]
    ) -> None:
        assert repair_action(series_type, Decimal(value), _coverage(9, total, largest)) == expected

    def test_a_heart_rate_series_is_deleted_only_over_stored_readings(self) -> None:
        # the other samples it covers are series, which may be all OW has of that span
        assert repair_action(SeriesType.heart_rate, Decimal("144.5"), _coverage(3, "432", instants=1)) == (
            "kept",
            None,
        )
        assert repair_action(SeriesType.heart_rate, Decimal("144.5"), _coverage(3, "432", instants=2)) == (
            "deleted",
            None,
        )

    def test_is_none_for_a_row_that_covers_too_few_samples_to_be_a_series(self) -> None:
        assert repair_action(SeriesType.active_energy, Decimal("3"), _coverage(1, "1.5")) is None
