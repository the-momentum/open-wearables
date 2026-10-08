"""Tests for the personal record schemas."""

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.model_crud.activities import PersonalRecordResponse, PersonalRecordUpdate, sex_to_db


class TestPersonalRecordUpdate:
    def test_accepts_past_birth_date(self) -> None:
        assert PersonalRecordUpdate(birth_date=date(1990, 5, 1)).birth_date == date(1990, 5, 1)

    def test_accepts_today(self) -> None:
        today = datetime.now(timezone.utc).date()
        assert PersonalRecordUpdate(birth_date=today).birth_date == today

    def test_rejects_future_birth_date(self) -> None:
        tomorrow = datetime.now(timezone.utc).date() + timedelta(days=1)
        with pytest.raises(ValidationError, match="birth_date cannot be in the future"):
            PersonalRecordUpdate(birth_date=tomorrow)

    def test_rejects_unknown_gender(self) -> None:
        with pytest.raises(ValidationError):
            PersonalRecordUpdate(gender="unknown")

    def test_rejects_unknown_sex(self) -> None:
        with pytest.raises(ValidationError):
            PersonalRecordUpdate(sex="other")

    def test_omitted_fields_are_null(self) -> None:
        payload = PersonalRecordUpdate()
        assert payload.birth_date is None
        assert payload.gender is None
        assert payload.sex is None


class TestPersonalRecordResponse:
    def test_has_no_record_id(self) -> None:
        response = PersonalRecordResponse(user_id=uuid4())
        assert set(response.model_dump()) == {"user_id", "birth_date", "gender", "sex"}

    @pytest.mark.parametrize(("stored", "shown"), [(True, "male"), (False, "female"), (None, None)])
    def test_reads_sex_from_the_stored_boolean(self, stored: bool | None, shown: str | None) -> None:
        assert PersonalRecordResponse(user_id=uuid4(), sex=stored).sex == shown


@pytest.mark.parametrize(("sex", "stored"), [("male", True), ("female", False), (None, None)])
def test_sex_to_db(sex: str | None, stored: bool | None) -> None:
    assert sex_to_db(sex) is stored
