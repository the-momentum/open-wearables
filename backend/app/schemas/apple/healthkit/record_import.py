# ruff: noqa: N815

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel

from app.constants.series_types.apple import (
    CATEGORY_TYPE_IDENTIFIERS,
    METRIC_TYPE_TO_SERIES_TYPE,
)

from .source_info import SourceInfo

# Extract all valid Apple HealthKit metric type keys for Literal type
# This ensures type safety and OpenAPI documentation
# Includes both quantity types (HKQuantityTypeIdentifier...) and category types (HKCategoryTypeIdentifier...)
_APPLE_METRIC_TYPE_KEYS = tuple(METRIC_TYPE_TO_SERIES_TYPE.keys()) + tuple(CATEGORY_TYPE_IDENTIFIERS)
AppleMetricType = Literal[_APPLE_METRIC_TYPE_KEYS]  # type: ignore[valid-type]


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
    type: AppleMetricType | None = None
    startDate: datetime
    endDate: datetime
    unit: str | None
    value: Decimal
    source: SourceInfo | None = None
    recordMetadata: list[dict[str, Any]] | None = None
