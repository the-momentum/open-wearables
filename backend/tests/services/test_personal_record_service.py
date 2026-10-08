"""Tests for PersonalRecordService."""

from datetime import date
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import PersonalRecord
from app.schemas.model_crud.activities import PersonalRecordUpdate
from app.services.personal_record_service import personal_record_service
from tests.factories import PersonalRecordFactory, UserFactory


class TestGetForUser:
    def test_without_record_returns_empty_unsaved_record(self, db: Session) -> None:
        user = UserFactory()

        record = personal_record_service.get_for_user(db, user.id)

        assert record.user_id == user.id
        assert record.birth_date is None
        assert record.gender is None
        assert record.sex is None
        assert db.query(PersonalRecord).filter(PersonalRecord.user_id == user.id).count() == 0

    def test_returns_existing_record(self, db: Session) -> None:
        existing = PersonalRecordFactory(birth_date=date(1990, 5, 1), gender="male")

        record = personal_record_service.get_for_user(db, existing.user_id)

        assert record.id == existing.id

    def test_unknown_user_raises_404(self, db: Session) -> None:
        with pytest.raises(HTTPException) as exc_info:
            personal_record_service.get_for_user(db, uuid4())
        assert exc_info.value.status_code == 404


class TestUpsertForUser:
    def test_stores_payload(self, db: Session) -> None:
        user = UserFactory()

        record = personal_record_service.upsert_for_user(
            db, user.id, PersonalRecordUpdate(birth_date=date(1990, 5, 1), gender="nonbinary", sex="male")
        )

        assert record.birth_date == date(1990, 5, 1)
        assert record.gender == "nonbinary"
        assert record.sex is True

    def test_unknown_user_raises_404(self, db: Session) -> None:
        with pytest.raises(HTTPException) as exc_info:
            personal_record_service.upsert_for_user(db, uuid4(), PersonalRecordUpdate())
        assert exc_info.value.status_code == 404
