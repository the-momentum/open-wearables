"""HealthKit condensed series at SDK ingest: dropped over originals OW holds, kept otherwise (#1983)."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.schemas.enums import SeriesType
from tests.factories import UserFactory
from tests.fixtures.healthkit_records import (
    ACTIVE_ENERGY,
    BASAL_ENERGY,
    DISTANCE,
    HEART_RATE,
    healthkit_record,
    load_healthkit_records,
    stored_samples,
)

OURA_APP = "com.ouraring.oura"
# A workout old enough for HealthKit to condense, and one that is not
OLD = (datetime.now(timezone.utc) - timedelta(days=120)).replace(second=0, microsecond=0)
RECENT = (datetime.now(timezone.utc) - timedelta(days=1)).replace(second=0, microsecond=0)


@pytest.fixture
def user_id() -> str:
    return str(UserFactory().id)


def _originals(start: datetime, kind: str = ACTIVE_ENERGY, value: str = "1.5", **source: Any) -> list[dict[str, Any]]:
    """Ten one-minute samples from start, as the watch writes them."""
    return [healthkit_record(kind, start + timedelta(minutes=minute), 60, value, **source) for minute in range(10)]


def _heart_rates(start: datetime) -> list[dict[str, Any]]:
    """Ten heart rate readings, one every 30 seconds from start."""
    return [healthkit_record(HEART_RATE, start + timedelta(seconds=second), 0, "140") for second in range(0, 300, 30)]


class TestCondensedSeriesAtIngest:
    @pytest.mark.parametrize(
        ("kind", "series_type", "minute_value", "series_value"),
        [
            (ACTIVE_ENERGY, SeriesType.active_energy, "1.5", "15"),
            (BASAL_ENERGY, SeriesType.basal_energy, "1.2", "12"),
            (DISTANCE, SeriesType.distance_walking_running, "80", "800"),
        ],
    )
    def test_a_series_over_stored_originals_is_dropped(
        self, db: Session, user_id: str, kind: str, series_type: SeriesType, minute_value: str, series_value: str
    ) -> None:
        load_healthkit_records(db, user_id, _originals(OLD, kind, minute_value))
        originals = stored_samples(db, series_type)

        load_healthkit_records(db, user_id, [healthkit_record(kind, OLD, 600, series_value)])

        assert len(originals) == 10
        assert stored_samples(db, series_type) == originals

    def test_a_series_without_stored_originals_is_kept(self, db: Session, user_id: str) -> None:
        load_healthkit_records(db, user_id, [healthkit_record(ACTIVE_ENERGY, OLD, 600, "15")])

        assert stored_samples(db) == [(OLD, 600, Decimal("15"))]

    def test_a_series_filed_under_the_iphones_model_is_dropped(self, db: Session, user_id: str) -> None:
        load_healthkit_records(db, user_id, _originals(OLD))
        originals = stored_samples(db)

        load_healthkit_records(
            db, user_id, [healthkit_record(ACTIVE_ENERGY, OLD, 600, "15", hardware="iPhone15,2", device_model="iPhone")]
        )

        assert stored_samples(db) == originals

    @pytest.mark.parametrize("count", [10, None], ids=["counted", "without a count"])
    def test_a_heart_rate_series_over_its_stored_readings_is_dropped(
        self, db: Session, user_id: str, count: int | None
    ) -> None:
        load_healthkit_records(db, user_id, _heart_rates(OLD))
        stored = stored_samples(db, SeriesType.heart_rate)

        load_healthkit_records(db, user_id, [healthkit_record(HEART_RATE, OLD, 300, "144.5", count=count)])

        assert len(stored) == 10
        assert stored_samples(db, SeriesType.heart_rate) == stored

    def test_a_counted_heart_rate_series_over_one_stored_reading_is_kept(self, db: Session, user_id: str) -> None:
        load_healthkit_records(db, user_id, [healthkit_record(HEART_RATE, OLD + timedelta(seconds=60), 0, "140")])

        load_healthkit_records(db, user_id, [healthkit_record(HEART_RATE, OLD, 300, "144", count=10)])

        assert (OLD, 300, Decimal("144")) in stored_samples(db, SeriesType.heart_rate)

    def test_a_series_condensed_again_over_the_one_kept_is_dropped(self, db: Session, user_id: str) -> None:
        load_healthkit_records(db, user_id, [healthkit_record(ACTIVE_ENERGY, OLD, 600, "15", count=10)])  # kept
        stored = stored_samples(db)

        load_healthkit_records(db, user_id, [healthkit_record(ACTIVE_ENERGY, OLD, 600, "15", count=10)])  # new id

        assert stored == [(OLD, 600, Decimal("15"))]
        assert stored_samples(db) == stored

    def test_a_counted_series_over_part_of_its_originals_is_kept(self, db: Session, user_id: str) -> None:
        load_healthkit_records(db, user_id, [healthkit_record(ACTIVE_ENERGY, OLD + timedelta(minutes=5), 60, "1.5")])

        load_healthkit_records(db, user_id, [healthkit_record(ACTIVE_ENERGY, OLD, 600, "15", count=10)])

        assert (OLD, 600, Decimal("15")) in stored_samples(db)

    def test_a_resent_sample_still_updates_its_stored_row(self, db: Session, user_id: str) -> None:
        load_healthkit_records(db, user_id, [healthkit_record(HEART_RATE, OLD + timedelta(seconds=60), 0, "140")])
        series = healthkit_record(HEART_RATE, OLD, 300, "144", record_id="SERIES-1")
        load_healthkit_records(db, user_id, [series])  # kept: it covers a single reading

        load_healthkit_records(db, user_id, [{**series, "value": "146"}])  # it covers that reading and itself

        assert (OLD, 300, Decimal("146")) in stored_samples(db, SeriesType.heart_rate)

    def test_a_recent_sample_is_not_checked(self, db: Session, user_id: str) -> None:
        load_healthkit_records(db, user_id, _originals(RECENT))

        load_healthkit_records(db, user_id, [healthkit_record(ACTIVE_ENERGY, RECENT, 600, "15")])

        assert (RECENT, 600, Decimal("15")) in stored_samples(db)

    def test_a_count_of_one_is_never_dropped(self, db: Session, user_id: str) -> None:
        load_healthkit_records(db, user_id, _originals(OLD))

        load_healthkit_records(db, user_id, [healthkit_record(ACTIVE_ENERGY, OLD, 600, "15", count=1)])

        assert (OLD, 600, Decimal("15")) in stored_samples(db)

    def test_a_third_party_source_is_never_dropped(self, db: Session, user_id: str) -> None:
        oura: dict[str, Any] = {"app_id": OURA_APP, "hardware": None, "device_model": "Oura Ring"}
        load_healthkit_records(db, user_id, _originals(OLD, **oura))

        load_healthkit_records(db, user_id, [healthkit_record(ACTIVE_ENERGY, OLD, 600, "15", **oura)])

        assert (OLD, 600, Decimal("15")) in stored_samples(db)

    def test_the_drop_is_logged_with_its_counts(self, db: Session, user_id: str) -> None:
        load_healthkit_records(db, user_id, _originals(OLD))

        with patch("app.services.sdk.condensed_series.logger") as logger:
            load_healthkit_records(db, user_id, [healthkit_record(ACTIVE_ENERGY, OLD, 600, "15")])

        logger.info.assert_called_once()
        assert logger.info.call_args.kwargs == {
            "action": "sdk_condensed_series_dropped",
            "user_id": user_id,
            "checked": 1,
            "by_type": {"active_energy": 1},
        }

    def test_only_the_condensed_series_leaves_a_mixed_batch(self, db: Session, user_id: str) -> None:
        load_healthkit_records(db, user_id, _originals(OLD))
        originals = stored_samples(db)
        later = OLD + timedelta(hours=2)

        result = load_healthkit_records(
            db,
            user_id,
            [
                healthkit_record(ACTIVE_ENERGY, OLD, 600, "15"),  # the series over the originals
                healthkit_record(ACTIVE_ENERGY, later, 600, "4"),  # an old sample that covers nothing
                healthkit_record(ACTIVE_ENERGY, RECENT, 600, "3"),  # a recent sample
            ],
        )

        assert stored_samples(db) == [*originals, (later, 600, Decimal("4")), (RECENT, 600, Decimal("3"))]
        assert (result["records_saved"], result["types"]) == (2, [SeriesType.active_energy.value])
