# ruff: noqa: N815

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from .source_info import SourceInfo


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
    source: SourceInfo | None = None


class RecordJSON(BaseModel):
    """Schema for JSON import format from HealthKit."""

    uuid: str | None = None
    user_id: str | None = None
    type: str | None = None
    startDate: datetime
    endDate: datetime
    unit: str | None
    value: Decimal
    source: SourceInfo | None = None
    recordMetadata: list[dict[str, Any]] | None = None
