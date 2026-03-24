from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


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


class PersonalRecordResponse(PersonalRecordBase):
    id: UUID
    user_id: UUID
