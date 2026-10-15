"""Tests for PersonalRecordRepository."""

from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.models import PersonalRecord
from app.repositories import PersonalRecordRepository
from tests.factories import PersonalRecordFactory, UserFactory


class TestPersonalRecordRepository:
    @pytest.fixture
    def repo(self) -> PersonalRecordRepository:
        return PersonalRecordRepository(PersonalRecord)

    def test_get_by_user_id_without_record(self, db: Session, repo: PersonalRecordRepository) -> None:
        user = UserFactory()
        assert repo.get_by_user_id(db, user.id) is None

    def test_get_by_user_id(self, db: Session, repo: PersonalRecordRepository) -> None:
        existing = PersonalRecordFactory(birth_date=date(1990, 5, 1))
        record = repo.get_by_user_id(db, existing.user_id)
        assert record is not None
        assert record.id == existing.id

    def test_upsert_creates_record(self, db: Session, repo: PersonalRecordRepository) -> None:
        user = UserFactory()

        record = repo.upsert(db, user.id, birth_date=date(1990, 5, 1), gender="female", sex=False)

        assert record.user_id == user.id
        assert record.birth_date == date(1990, 5, 1)
        assert record.gender == "female"
        assert record.sex is False

    def test_upsert_replaces_fields_of_existing_record(self, db: Session, repo: PersonalRecordRepository) -> None:
        existing = PersonalRecordFactory(birth_date=date(1990, 5, 1), gender="female", sex=True)

        record = repo.upsert(db, existing.user_id, birth_date=date(1991, 1, 1), gender=None, sex=None)

        assert record.id == existing.id
        assert record.birth_date == date(1991, 1, 1)
        assert record.gender is None
        assert record.sex is None
        assert db.query(PersonalRecord).filter(PersonalRecord.user_id == existing.user_id).count() == 1
