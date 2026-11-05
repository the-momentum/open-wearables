"""Which SDK samples may be HealthKit condensed series, and which of them repeat samples OW holds."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.repositories.data_point_series_repository import Coverage
from app.schemas.enums import SeriesType
from app.schemas.model_crud.activities import TimeSeriesSampleCreate
from app.services.sdk.condensed_series import is_candidate, is_condensed, repair_action

NOW = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)
WATCH_APP = "com.apple.health.5C1B9A4E-0D7E-4F7B-9E8A-2E3D4C5B6A70"


def _sample(
    series_type: SeriesType = SeriesType.active_energy,
    *,
    days_ago: int = 120,
    window: int | None = 600,
    app_id: str | None = WATCH_APP,
    value: str = "15",
) -> TimeSeriesSampleCreate:
    return TimeSeriesSampleCreate(
        id=uuid4(),
        user_id=uuid4(),
        source_app_id=app_id,
        recorded_at=NOW - timedelta(days=days_ago),
        window_seconds=window,
        value=Decimal(value),
        series_type=series_type,
    )


def _coverage(covered: int, total: str) -> Coverage:
    return Coverage(covered, Decimal(total), Decimal(total))


class TestIsCandidate:
    def test_an_old_windowed_sample_of_an_apple_device(self) -> None:
        assert is_candidate(_sample(), None, NOW)

    @pytest.mark.parametrize("count", [None, 4])
    @pytest.mark.parametrize(
        "sample",
        [_sample(window=None), _sample(app_id="com.ouraring.oura"), _sample(app_id=None), _sample(days_ago=29)],
        ids=["no window", "third-party app", "no app", "recent"],
    )
    def test_nothing_else_is_whatever_the_count(self, sample: TimeSeriesSampleCreate, count: int | None) -> None:
        assert not is_candidate(sample, count, NOW)

    def test_without_a_count_a_type_apple_does_not_condense_is_not(self) -> None:
        assert not is_candidate(_sample(SeriesType.steps), None, NOW)

    def test_a_count_decides_whatever_the_type(self) -> None:
        assert is_candidate(_sample(SeriesType.steps), 4, NOW)
        assert not is_candidate(_sample(), 1, NOW)

    def test_a_naive_recorded_at_reads_as_utc(self) -> None:
        sample = _sample()
        naive = sample.model_copy(update={"recorded_at": sample.recorded_at.replace(tzinfo=None)})
        assert is_candidate(naive, None, NOW)


class TestIsCondensed:
    def test_with_a_count_one_covered_sample_is_enough(self) -> None:
        assert is_condensed(_sample(SeriesType.heart_rate, value="148.3"), 4, _coverage(1, "140"))
        assert not is_condensed(_sample(SeriesType.heart_rate, value="148.3"), 4, _coverage(0, "0"))

    def test_with_a_count_a_cumulative_series_must_match_what_it_covers(self) -> None:
        assert not is_condensed(_sample(value="15"), 10, _coverage(1, "1.5"))  # part of its originals
        assert is_condensed(_sample(value="15"), 10, _coverage(10, "15"))

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
def test_repair_action_decides_by_what_the_series_has_over_the_sum(
    series_type: SeriesType, value: str, total: str, largest: str, expected: tuple[str, Decimal | None]
) -> None:
    coverage = Coverage(9, Decimal(total), Decimal(largest))

    assert repair_action(series_type, Decimal(value), coverage) == expected
