"""HealthKit condensed series at SDK ingest: dropped over originals OW holds, kept otherwise (#1983)."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import SeriesSample
from app.schemas.enums import SeriesType, get_series_type_id
from app.services.sdk.import_service import ImportService, LoadDataResult
from tests.factories import UserFactory

WATCH_APP = "com.apple.health.5C1B9A4E-0D7E-4F7B-9E8A-2E3D4C5B6A70"
OURA_APP = "com.ouraring.oura"
ACTIVE_ENERGY = "HKQuantityTypeIdentifierActiveEnergyBurned"
HEART_RATE = "HKQuantityTypeIdentifierHeartRate"
UNITS = {ACTIVE_ENERGY: "kcal", HEART_RATE: "count/min"}
# A workout old enough for HealthKit to condense, and one that is not
OLD = (datetime.now(timezone.utc) - timedelta(days=120)).replace(second=0, microsecond=0)
RECENT = (datetime.now(timezone.utc) - timedelta(days=1)).replace(second=0, microsecond=0)


def _iso(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _record(
    kind: str,
    start: datetime,
    seconds: int,
    value: str,
    *,
    count: int | None = None,
    record_id: str | None = None,
    app_id: str = WATCH_APP,
    hardware: str | None = "Watch6,18",
    device_model: str = "Watch",
) -> dict[str, Any]:
    """A HealthKit record as the SDK sends it; the hardware version names the device of Apple's own sources."""
    source: dict[str, Any] = {"appId": app_id, "name": "Test Apple Watch", "deviceModel": device_model}
    if hardware:
        source["deviceHardwareVersion"] = hardware
    record: dict[str, Any] = {
        "id": record_id or str(uuid4()).upper(),
        "type": kind,
        "unit": UNITS[kind],
        "value": value,
        "startDate": _iso(start),
        "endDate": _iso(start + timedelta(seconds=seconds)),
        "source": source,
    }
    if count is not None:
        record["count"] = count
    return record


def _load(db: Session, user_id: str, records: list[dict[str, Any]]) -> LoadDataResult:
    payload = {
        "provider": "apple",
        "sdkVersion": "0.17.0",
        "syncTimestamp": _iso(datetime.now(timezone.utc)),
        "data": {"records": records},
    }
    return ImportService().load_data(db, payload, user_id)


def _originals(start: datetime, **source: Any) -> list[dict[str, Any]]:
    """A workout's active energy as the watch writes it: 1.5 kcal a minute for 10 minutes."""
    return [_record(ACTIVE_ENERGY, start + timedelta(minutes=minute), 60, "1.5", **source) for minute in range(10)]


def _stored(
    db: Session, series_type: SeriesType = SeriesType.active_energy
) -> list[tuple[datetime, int | None, Decimal]]:
    db.expire_all()
    rows = (
        db.query(SeriesSample)
        .filter(SeriesSample.series_type_definition_id == get_series_type_id(series_type))
        .order_by(SeriesSample.recorded_at)
        .all()
    )
    return [(row.recorded_at, row.window_seconds, row.value) for row in rows]


class TestCondensedSeriesAtIngest:
    def test_a_series_over_stored_originals_is_dropped(self, db: Session) -> None:
        user_id = str(UserFactory().id)
        _load(db, user_id, _originals(OLD))
        originals = _stored(db)

        _load(db, user_id, [_record(ACTIVE_ENERGY, OLD, 600, "15")])

        assert len(originals) == 10
        assert _stored(db) == originals

    def test_a_series_without_stored_originals_is_kept(self, db: Session) -> None:
        user_id = str(UserFactory().id)

        _load(db, user_id, [_record(ACTIVE_ENERGY, OLD, 600, "15")])

        assert _stored(db) == [(OLD, 600, Decimal("15"))]

    def test_a_series_filed_under_the_iphones_model_is_dropped(self, db: Session) -> None:
        user_id = str(UserFactory().id)
        _load(db, user_id, _originals(OLD))
        originals = _stored(db)

        _load(db, user_id, [_record(ACTIVE_ENERGY, OLD, 600, "15", hardware="iPhone15,2", device_model="iPhone")])

        assert _stored(db) == originals

    def test_a_count_above_one_drops_a_series_over_a_single_stored_sample(self, db: Session) -> None:
        user_id = str(UserFactory().id)
        _load(db, user_id, [_record(ACTIVE_ENERGY, OLD + timedelta(minutes=5), 60, "1.5")])
        stored = _stored(db)

        _load(db, user_id, [_record(ACTIVE_ENERGY, OLD, 600, "15", count=10)])

        assert _stored(db) == stored

    def test_a_heart_rate_series_over_stored_readings_is_dropped(self, db: Session) -> None:
        user_id = str(UserFactory().id)
        readings = [_record(HEART_RATE, OLD + timedelta(seconds=second), 0, "140") for second in range(0, 300, 30)]
        _load(db, user_id, readings)
        stored = _stored(db, SeriesType.heart_rate)

        _load(db, user_id, [_record(HEART_RATE, OLD, 300, "144.5")])

        assert _stored(db, SeriesType.heart_rate) == stored

    def test_a_resent_sample_still_updates_its_stored_row(self, db: Session) -> None:
        user_id = str(UserFactory().id)
        _load(db, user_id, [_record(HEART_RATE, OLD + timedelta(seconds=60), 0, "140")])
        series = _record(HEART_RATE, OLD, 300, "144", record_id="SERIES-1")
        _load(db, user_id, [series])  # kept: it covers a single reading

        _load(db, user_id, [{**series, "value": "146"}])  # it covers that reading and itself

        assert (OLD, 300, Decimal("146")) in _stored(db, SeriesType.heart_rate)

    def test_a_recent_sample_is_not_checked(self, db: Session) -> None:
        user_id = str(UserFactory().id)
        _load(db, user_id, _originals(RECENT))

        _load(db, user_id, [_record(ACTIVE_ENERGY, RECENT, 600, "15")])

        assert (RECENT, 600, Decimal("15")) in _stored(db)

    def test_a_count_of_one_is_never_dropped(self, db: Session) -> None:
        user_id = str(UserFactory().id)
        _load(db, user_id, _originals(OLD))

        _load(db, user_id, [_record(ACTIVE_ENERGY, OLD, 600, "15", count=1)])

        assert (OLD, 600, Decimal("15")) in _stored(db)

    def test_a_third_party_source_is_never_dropped(self, db: Session) -> None:
        user_id = str(UserFactory().id)
        oura: dict[str, Any] = {"app_id": OURA_APP, "hardware": None, "device_model": "Oura Ring"}
        _load(db, user_id, _originals(OLD, **oura))

        _load(db, user_id, [_record(ACTIVE_ENERGY, OLD, 600, "15", **oura)])

        assert (OLD, 600, Decimal("15")) in _stored(db)

    def test_the_drop_is_logged_with_its_counts(self, db: Session) -> None:
        user_id = str(UserFactory().id)
        _load(db, user_id, _originals(OLD))

        with patch("app.services.sdk.condensed_series.logger") as logger:
            _load(db, user_id, [_record(ACTIVE_ENERGY, OLD, 600, "15")])

        logger.info.assert_called_once()
        assert logger.info.call_args.kwargs == {
            "action": "sdk_condensed_series_dropped",
            "user_id": user_id,
            "checked": 1,
            "by_type": {"active_energy": 1},
        }

    def test_only_the_condensed_series_leaves_a_mixed_batch(self, db: Session) -> None:
        user_id = str(UserFactory().id)
        _load(db, user_id, _originals(OLD))
        originals = _stored(db)
        later = OLD + timedelta(hours=2)

        result = _load(
            db,
            user_id,
            [
                _record(ACTIVE_ENERGY, OLD, 600, "15"),  # the series over the originals
                _record(ACTIVE_ENERGY, later, 600, "4"),  # an old sample that covers nothing
                _record(ACTIVE_ENERGY, RECENT, 600, "3"),  # a recent sample
            ],
        )

        assert _stored(db) == [*originals, (later, 600, Decimal("4")), (RECENT, 600, Decimal("3"))]
        assert (result["records_saved"], result["types"]) == (2, [SeriesType.active_energy.value])
