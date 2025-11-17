from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class MetadataEntryIn(BaseModel):
    """Schema for metadata entry."""
    key: str
    value: Decimal


class RecordBase(BaseModel):
    """Base schema for record."""
    type: str
    startDate: datetime
    endDate: datetime
    unit: str
    value: Decimal
    sourceName: str


class RecordIn(RecordBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    provider_id: UUID | None = None
    user_id: str | None = None
    recordMetadata: list[MetadataEntryIn] | None = None


class RecordJSON(BaseModel):
    """Schema for JSON import format from HealthKit."""
    uuid: str | None = None
    user_id: str | None = None
    type: str | None = None
    startDate: datetime
    endDate: datetime
    unit: str
    value: Decimal
    sourceName: str | None = None
    recordMetadata: list[dict[str, Any]] | None = None



