"""Apple menstrual-flow category samples must remain available through cycle events."""

from logging import getLogger
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DataSource, EventRecord, MenstrualCycleDetails
from app.schemas.model_crud.activities import EventRecordQueryParams
from app.services.event_record_service import event_record_service
from app.services.sdk.import_service import ImportService, _menstrual_cycle_start
from tests.factories import UserFactory


def flow_record(day: int, value: int, source: str = "Health") -> dict:
    return {
        "id": str(uuid4()),
        "type": "HKCategoryTypeIdentifierMenstrualFlow",
        "value": value,
        "unit": None,
        "startDate": f"2026-09-{day:02d}T00:00:00+07:00",
        "endDate": f"2026-09-{day + 1:02d}T00:00:00+07:00",
        "zoneOffset": "+07:00",
        "source": {"name": source},
        "metadata": {"HKMetadataKeyMenstrualCycleStart": str(day == 1).lower()},
    }


def test_cycle_start_metadata_accepts_sdk_and_healthkit_shapes() -> None:
    key = "HKMetadataKeyMenstrualCycleStart"
    assert _menstrual_cycle_start({key: "true"}) is True
    assert _menstrual_cycle_start({key: False}) is False
    assert _menstrual_cycle_start([{"key": key, "value": "false"}]) is False
    assert _menstrual_cycle_start({"unrelated": "true"}) is None


def test_menstrual_flow_is_saved_once_and_exposed_by_cycle_api(db: Session) -> None:
    user = UserFactory()
    payload = {
        "provider": "apple",
        "sdkVersion": "1.0.0",
        "syncTimestamp": "2026-09-06T12:00:00Z",
        "data": {"records": [flow_record(1, 2), flow_record(2, 3), flow_record(3, 5)]},
    }
    service = ImportService(log=getLogger(__name__))
    first = service.load_data(db, payload, str(user.id))
    second = service.load_data(db, payload, str(user.id))

    assert first["records_saved"] == 3
    assert second["records_saved"] == 0
    assert first["types"] == ["menstrual_flow"]
    records = db.execute(
        select(EventRecord, DataSource)
        .join(DataSource, EventRecord.data_source_id == DataSource.id)
        .where(DataSource.user_id == user.id)
    ).all()
    assert len(records) == 3
    assert all(record.category == "menstrual_cycle" and source.provider == "apple" for record, source in records)
    assert all(record.type == "period_flow" for record, _ in records)

    result = event_record_service.get_menstrual_cycles(db, user.id, EventRecordQueryParams(category="menstrual_cycle"))
    assert len(result.data) == 3
    assert all(row.source.provider == "apple" for row in result.data)
    by_day = {row.start_time.day: row for row in result.data}
    assert by_day[1].flow_intensity == "light"
    assert by_day[1].is_cycle_start is True
    assert by_day[2].flow_intensity == "medium"
    assert by_day[2].is_cycle_start is False
    assert by_day[3].flow_intensity == "none"
    assert by_day[3].is_cycle_start is False
    assert db.query(MenstrualCycleDetails).count() == 3


def test_resync_adds_details_to_existing_flow_record(db: Session) -> None:
    user = UserFactory()
    record = flow_record(1, 4)
    payload = {
        "provider": "apple",
        "sdkVersion": "1.0.0",
        "syncTimestamp": "2026-09-06T12:00:00Z",
        "data": {"records": [record]},
    }
    service = ImportService(log=getLogger(__name__))
    first = service.load_data(db, payload, str(user.id))
    assert first["records_saved"] == 1
    saved = db.scalar(select(EventRecord).where(EventRecord.external_id == record["id"]))
    assert saved is not None
    db.query(MenstrualCycleDetails).filter(MenstrualCycleDetails.record_id == saved.id).delete()
    db.commit()

    second = service.load_data(db, payload, str(user.id))
    assert second["records_saved"] == 0
    details = db.scalar(select(MenstrualCycleDetails).where(MenstrualCycleDetails.record_id == saved.id))
    assert details is not None
    assert details.flow_intensity == "heavy"
    assert details.is_cycle_start is True
