from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from app.schemas.apple.common import DateRange


class MetadataEntryResponse(BaseModel):
    """Metadata entry response model."""
    
    id: str
    key: str
    value: Decimal


class RecordResponse(BaseModel):
    """Individual HealthKit record response model - matches unified database model."""

    id: UUID
    type: str
    sourceName: str
    startDate: datetime
    endDate: datetime
    unit: str
    value: Decimal
    user_id: str
    recordMetadata: list[MetadataEntryResponse] = []



class RecordMeta(BaseModel):
    """Metadata for HealthKit record response."""

    requested_at: str  # ISO 8601
    filters: dict
    result_count: int
    total_count: int
    date_range: DateRange


class RecordListResponse(BaseModel):
    """Response model for HealthKit record list endpoint."""

    data: list[RecordResponse]
    meta: RecordMeta
