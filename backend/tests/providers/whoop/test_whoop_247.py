from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import EventRecordAggregate
from app.schemas.enums import SeriesType, get_series_type_id
from app.schemas.model_crud.activities import CalendarPeriod
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
