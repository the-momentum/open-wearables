from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models import EventRecordAggregate
from app.schemas.enums import SeriesType, get_series_type_id
from app.schemas.model_crud.activities import CalendarPeriod, EventRecordDetailCreate
from app.services.providers.whoop.data_247 import Whoop247Data
from app.services.providers.whoop.strategy import WhoopStrategy


def test_cycle_day_values_carry_the_local_day_the_cycle_covers() -> None:
    raw_cycle = {
        "score_state": "SCORED",
        "start": "2026-03-10T22:30:00.000Z",
        "end": "2026-03-11T22:10:00.000Z",
        "timezone_offset": "+01:00",
        "score": {"kilojoule": 8368, "strain": 10.2},
        "step_count": 9000,
    }

    samples, _ = WhoopStrategy().data_247.normalize_cycle(raw_cycle, uuid4())

    local_midnight = datetime(2026, 3, 10, 23, tzinfo=timezone.utc)
    assert {s.period for s in samples} == {CalendarPeriod.local_day(local_midnight, zone_offset="+01:00")}


def test_recovery_values_point_at_the_sleep_they_were_scored_on(db: Session) -> None:
    from tests.factories import DataSourceFactory, EventRecordFactory, UserFactory

    user = UserFactory()
    sleep = EventRecordFactory(
        category="sleep", external_id="whoop-sleep-1", data_source=DataSourceFactory(user=user, provider="whoop")
    )
    data_247 = WhoopStrategy().data_247
    normalized, _ = data_247.normalize_recovery(
        {
            "sleep_id": "whoop-sleep-1",
            "score_state": "SCORED",
            "created_at": "2026-03-11T06:40:00.000Z",
            "score": {"resting_heart_rate": 52, "spo2_percentage": 97.5},
        },
        user.id,
    )

    data_247.save_recovery_data(db, user.id, normalized)

    rows = {row.series_type_definition_id: row for row in db.query(EventRecordAggregate)}
    assert {row.record_id for row in rows.values()} == {sleep.id}
    assert rows[get_series_type_id(SeriesType.resting_heart_rate)].avg == Decimal("52")
    assert rows[get_series_type_id(SeriesType.oxygen_saturation)].avg == Decimal("97.5")


def _recovery(user_id: object, sleep_id: str) -> dict:
    normalized, _ = WhoopStrategy().data_247.normalize_recovery(
        {
            "sleep_id": sleep_id,
            "score_state": "SCORED",
            "created_at": "2026-03-11T06:40:00.000Z",
            "score": {"resting_heart_rate": 52},
        },
        user_id,
    )
    return normalized


def test_a_recovery_whose_sleep_merged_away_lands_on_the_sleep_it_merged_into(db: Session) -> None:
    from tests.factories import DataSourceFactory, EventRecordFactory, UserFactory

    user = UserFactory()
    merged = EventRecordFactory(
        category="sleep",
        external_id="whoop-sleep-1",
        data_source=DataSourceFactory(user=user, provider="whoop"),
        start_datetime=datetime(2026, 3, 10, 22, tzinfo=timezone.utc),
        end_datetime=datetime(2026, 3, 11, 6, 20, tzinfo=timezone.utc),
    )

    WhoopStrategy().data_247.save_recovery_data(db, user.id, _recovery(user.id, "whoop-sleep-2"))

    assert [row.record_id for row in db.query(EventRecordAggregate)] == [merged.id]


def test_a_recovery_whose_sleep_is_not_synced_yet_stays_unlinked(db: Session) -> None:
    from tests.factories import DataSourceFactory, EventRecordFactory, UserFactory

    user = UserFactory()
    # The night before: no sleep of this night has arrived yet.
    EventRecordFactory(
        category="sleep",
        external_id="whoop-sleep-0",
        data_source=DataSourceFactory(user=user, provider="whoop"),
        start_datetime=datetime(2026, 3, 9, 22, tzinfo=timezone.utc),
        end_datetime=datetime(2026, 3, 10, 6, 30, tzinfo=timezone.utc),
    )

    WhoopStrategy().data_247.save_recovery_data(db, user.id, _recovery(user.id, "whoop-sleep-2"))

    assert db.query(EventRecordAggregate).count() == 0


@pytest.fixture
def data_247() -> Whoop247Data:
    instance = WhoopStrategy().data_247
    assert isinstance(instance, Whoop247Data)
    return instance


def _raw_sleep(**overrides: Any) -> dict[str, Any]:
    raw = {
        "id": str(uuid4()),
        "cycle_id": 93845,
        "start": "2024-01-14T23:00:00.000Z",
        "end": "2024-01-15T07:00:00.000Z",
        "timezone_offset": "+00:00",
        "nap": False,
        "score_state": "SCORED",
        "score": {
            "stage_summary": {
                "total_in_bed_time_milli": 28_800_000,
                "total_awake_time_milli": 1_800_000,
                "total_light_sleep_time_milli": 14_400_000,
                "total_slow_wave_sleep_time_milli": 5_400_000,
                "total_rem_sleep_time_milli": 7_200_000,
            },
            "sleep_efficiency_percentage": 91.5,
        },
    }
    raw.update(overrides)
    return raw


def _saved_detail(data_247: Whoop247Data, raw: dict[str, Any]) -> EventRecordDetailCreate:
    normalized, _ = data_247.normalize_sleep(raw, uuid4())
    with patch("app.services.providers.whoop.data_247.event_record_service") as mock_event:
        data_247.save_sleep_data(MagicMock(), uuid4(), normalized)
    return mock_event.create_or_merge_sleep.call_args[0][3]


class TestWhoopSleepStages:
    def test_scored_sleep_saves_stage_minutes(self, data_247: Whoop247Data) -> None:
        detail = _saved_detail(data_247, _raw_sleep())

        assert detail.sleep_deep_minutes == 90
        assert detail.sleep_light_minutes == 240
        assert detail.sleep_rem_minutes == 120
        assert detail.sleep_awake_minutes == 30
        assert detail.sleep_total_duration_minutes == 450
        assert detail.sleep_time_in_bed_minutes == 480

    def test_scored_nap_keeps_reported_zero_stages(self, data_247: Whoop247Data) -> None:
        raw = _raw_sleep(nap=True)
        raw["score"]["stage_summary"].update(total_rem_sleep_time_milli=0, total_awake_time_milli=0)

        detail = _saved_detail(data_247, raw)

        assert detail.sleep_rem_minutes == 0
        assert detail.sleep_awake_minutes == 0

    def test_pending_score_leaves_stages_unreported(self, data_247: Whoop247Data) -> None:
        raw = _raw_sleep(score_state="PENDING_SCORE")
        del raw["score"]

        detail = _saved_detail(data_247, raw)

        assert detail.sleep_deep_minutes is None
        assert detail.sleep_light_minutes is None
        assert detail.sleep_rem_minutes is None
        assert detail.sleep_awake_minutes is None
        assert detail.sleep_total_duration_minutes is None
        # Time in bed still falls back to the session window
        assert detail.sleep_time_in_bed_minutes == 480
