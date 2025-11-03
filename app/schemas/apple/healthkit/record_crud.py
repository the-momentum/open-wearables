from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class RecordCreate(BaseModel):
    """Schema for creating a record."""

    id: int | None = None
    user_id: UUID
    type: str
    startDate: datetime
    endDate: datetime
    unit: str
    value: Decimal
    sourceName: str


class RecordUpdate(BaseModel):
    """Schema for updating a record."""

    type: str | None = None
    startDate: datetime | None = None
    endDate: datetime | None = None
    unit: str | None = None
    value: Decimal | None = None
    sourceName: str | None = None
