from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from app.schemas.model_crud.activities import PersonalRecordUpsert


def test_upsert_accepts_valid_birth_date_and_gender():
    schema = PersonalRecordUpsert(birth_date=date(1990, 5, 17), gender="male")
    assert schema.birth_date == date(1990, 5, 17)
    assert schema.gender == "male"


def test_upsert_allows_all_fields_none():
    schema = PersonalRecordUpsert()
    assert schema.birth_date is None
    assert schema.gender is None


def test_upsert_rejects_future_birth_date():
    future = date.today() + timedelta(days=1)
    with pytest.raises(ValidationError):
        PersonalRecordUpsert(birth_date=future)


def test_upsert_rejects_implausibly_old_birth_date():
    with pytest.raises(ValidationError):
        PersonalRecordUpsert(birth_date=date(date.today().year - 121, 1, 1))


def test_upsert_rejects_unknown_gender():
    with pytest.raises(ValidationError):
        PersonalRecordUpsert(gender="unknown")
