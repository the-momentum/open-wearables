from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.schemas.model_crud.activities import PersonalRecordUpsert
from app.services.personal_record_service import personal_record_service
from app.utils.exceptions import ResourceNotFoundError
from tests.factories import UserFactory


def test_upsert_creates_when_absent(db: Session) -> None:
    user = UserFactory()
    record, created = personal_record_service.upsert(
        db, user.id, PersonalRecordUpsert(birth_date=date(1990, 1, 2), gender="female")
    )
    assert created is True
    assert record.user_id == user.id
    assert record.birth_date == date(1990, 1, 2)
    assert record.gender == "female"


def test_upsert_updates_when_present_without_duplicate(db: Session) -> None:
    user = UserFactory()
    first, created_first = personal_record_service.upsert(
        db, user.id, PersonalRecordUpsert(birth_date=date(1990, 1, 2))
    )
    second, created_second = personal_record_service.upsert(
        db, user.id, PersonalRecordUpsert(birth_date=date(1985, 6, 6), gender="male")
    )

    assert created_first is True
    assert created_second is False
    assert second.id == first.id  # same row, no duplicate
    assert second.birth_date == date(1985, 6, 6)
    assert second.gender == "male"

    all_for_user = db.query(type(second)).filter(type(second).user_id == user.id).all()
    assert len(all_for_user) == 1


def test_upsert_unknown_user_raises_not_found(db: Session) -> None:
    with pytest.raises(ResourceNotFoundError):
        personal_record_service.upsert(db, uuid4(), PersonalRecordUpsert(birth_date=date(1990, 1, 2)))


def test_get_for_user_returns_none_when_absent(db: Session) -> None:
    user = UserFactory()
    assert personal_record_service.get_for_user(db, user.id) is None


def test_get_for_user_raise_404_when_absent(db: Session) -> None:
    user = UserFactory()
    with pytest.raises(ResourceNotFoundError):
        personal_record_service.get_for_user(db, user.id, raise_404=True)
