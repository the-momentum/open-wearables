from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_HUMAN_AGE_YEARS = 120


class PersonalRecordBase(BaseModel):
    birth_date: date | None = Field(None, description="Birth date of the user")
    gender: Literal["female", "male", "nonbinary", "other"] | None = Field(
        None,
        description="Optional self-reported gender",
    )


class PersonalRecordCreate(PersonalRecordBase):
    id: UUID
    user_id: UUID


class PersonalRecordUpdate(PersonalRecordBase): ...


class PersonalRecordUpsert(PersonalRecordBase):
    """Write body for the upsert endpoint (user_id comes from the path, id is server-generated)."""

    @field_validator("birth_date")
    @classmethod
    def _birth_date_is_plausible(cls, value: date | None) -> date | None:
        if value is None:
            return value
        today = date.today()
        if value > today:
            raise ValueError("birth_date cannot be in the future")
        if value.year < today.year - MAX_HUMAN_AGE_YEARS:
            raise ValueError("birth_date is implausibly old")
        return value


class PersonalRecordResponse(PersonalRecordBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
