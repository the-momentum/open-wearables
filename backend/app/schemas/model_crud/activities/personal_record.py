from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
from pydantic_core import PydanticCustomError

Sex = Literal["female", "male"]

_SEX_DESCRIPTION = "Biological sex, for norms that differ between women and men"


def sex_to_db(sex: Sex | None) -> bool | None:
    """`personal_record.sex` is stored as a boolean: True = male, False = female, None = unknown."""
    return None if sex is None else sex == "male"


class PersonalRecordBase(BaseModel):
    birth_date: date | None = Field(None, description="Birth date of the user")
    gender: Literal["female", "male", "nonbinary", "other"] | None = Field(
        None,
        description="Optional self-reported gender",
    )


class PersonalRecordCreate(PersonalRecordBase):
    id: UUID
    user_id: UUID


class PersonalRecordUpdate(PersonalRecordBase):
    """The whole record: a field left out is stored as null."""

    sex: Sex | None = Field(None, description=_SEX_DESCRIPTION)

    @field_validator("birth_date")
    @classmethod
    def birth_date_not_in_future(cls, value: date | None) -> date | None:
        if value is not None and value > datetime.now(timezone.utc).date():
            raise PydanticCustomError("birth_date_in_future", "birth_date cannot be in the future")
        return value


class PersonalRecordResponse(PersonalRecordBase):
    user_id: UUID
    sex: Sex | None = Field(None, description=_SEX_DESCRIPTION)

    @field_validator("sex", mode="before")
    @classmethod
    def sex_from_db(cls, value: Any) -> Any:
        """Reads the stored boolean (see `sex_to_db`)."""
        if isinstance(value, bool):
            return "male" if value else "female"
        return value
