from datetime import date
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import PersonalRecord
from app.repositories.personal_record_repository import PersonalRecordRepository
from tests.factories import UserFactory


def test_get_by_user_id_returns_none_when_absent(db: Session) -> None:
    repo = PersonalRecordRepository(PersonalRecord)
    assert repo.get_by_user_id(db, uuid4()) is None


def test_get_by_user_id_returns_row_when_present(db: Session) -> None:
    user = UserFactory()
    record = PersonalRecord(id=uuid4(), user_id=user.id, birth_date=date(1988, 3, 1))
    db.add(record)
    db.commit()

    repo = PersonalRecordRepository(PersonalRecord)
    found = repo.get_by_user_id(db, user.id)
    assert found is not None
    assert found.user_id == user.id
    assert found.birth_date == date(1988, 3, 1)
