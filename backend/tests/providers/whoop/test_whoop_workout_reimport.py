from typing import Any
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants.workout_types.whoop import get_unified_workout_type
from app.models import EventRecord, WorkoutDetails
from app.schemas.enums import WorkoutType
from app.services.event_record_service import event_record_service
from app.services.providers.whoop.workouts import WhoopWorkouts
from tests.factories import UserFactory


@pytest.mark.parametrize(
    ("name", "expected"),
    [("weightlifting_msk", WorkoutType.STRENGTH_TRAINING), ("foam_rolling", WorkoutType.RECOVERY)],
)
def test_workout_alias_without_deprecated_sport_id(name: str, expected: WorkoutType) -> None:
    assert get_unified_workout_type(name) == expected
    assert get_unified_workout_type(f" {name.upper()} ") == expected


@pytest.mark.parametrize("single", [False, True])
def test_reimport_reuses_workout_details(db: Session, monkeypatch: pytest.MonkeyPatch, single: bool) -> None:
    user = UserFactory()
    workout_id = str(uuid4())
    raw: dict[str, Any] = {
        "id": workout_id,
        "user_id": 123,
        "created_at": "2026-09-01T09:00:00Z",
        "updated_at": "2026-09-01T09:00:00Z",
        "start": "2026-09-01T08:00:00Z",
        "end": "2026-09-01T09:00:00Z",
        "sport_name": "weightlifting_msk",
        "score_state": "SCORED",
        "score": {"strain": 8.5, "average_heart_rate": 120, "max_heart_rate": 160, "kilojoule": 900},
    }
    provider = WhoopWorkouts(
        workout_repo=Mock(),
        connection_repo=Mock(),
        provider_name="whoop",
        api_base_url="https://example.com",
        oauth=Mock(),
    )
    monkeypatch.setattr(provider, "get_workouts_from_api", Mock(return_value={"records": [raw]}))
    monkeypatch.setattr(provider, "get_workout_detail_from_api", Mock(return_value=raw))
    monkeypatch.setattr("app.services.providers.whoop.workouts.store_raw_payload", Mock())
    create_detail = Mock(wraps=event_record_service.create_detail)
    monkeypatch.setattr(event_record_service, "create_detail", create_detail)

    for _ in range(2):
        result = provider.load_single_workout(db, user.id, workout_id) if single else provider.load_data(db, user.id)
        assert result == 1

    assert create_detail.call_count == 1
    events = db.scalars(select(EventRecord).where(EventRecord.external_id == workout_id)).all()
    assert len(events) == 1
    details = db.scalars(select(WorkoutDetails).where(WorkoutDetails.record_id == events[0].id)).all()
    assert len(details) == 1
    assert details[0].heart_rate_avg == 120
