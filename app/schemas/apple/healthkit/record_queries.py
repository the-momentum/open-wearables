from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.schemas.apple.common import BaseQueryParams


class RecordQueryParams(BaseQueryParams):
    """Query parameters for HealthKit record filtering and pagination."""

    record_type: str | None = Field(
        None, description="Record type (e.g., 'HKQuantityTypeIdentifierStepCount', 'HKQuantityTypeIdentifierHeartRate')"
    )
    source_name: str | None = Field(
        None, description="Source name of the record (e.g., 'Apple Watch', 'iPhone')"
    )
    unit: str | None = Field(
        None, description="Unit of measurement (e.g., 'count', 'bpm', 'cal')"
    )
    min_value: float | None = Field(
        None, description="Minimum value"
    )
    max_value: float | None = Field(
        None, description="Maximum value"
    )
    sort_by: Literal["startDate", "endDate", "value", "type", "sourceName", "unit"] | None = Field(
        "startDate", description="Sort field"
    )
