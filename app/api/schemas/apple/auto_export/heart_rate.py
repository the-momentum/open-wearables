from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class HeartRateQueryParams(BaseModel):
    """Query parameters for heart rate filtering and pagination."""

    start_date: str | None = Field(
        None, description="ISO 8601 format (e.g., '2023-12-01T00:00:00Z')"
    )
    end_date: str | None = Field(
        None, description="ISO 8601 format (e.g., '2023-12-31T23:59:59Z')"
    )
    workout_id: UUID | None = Field(
        None, description="Filter by specific workout ID"
    )
    source: str | None = Field(
        None, description="Filter by data source (e.g., 'Apple Health')"
    )
    min_avg: float | None = Field(None, description="Minimum average heart rate")
    max_avg: float | None = Field(None, description="Maximum average heart rate")
    min_max: float | None = Field(None, description="Minimum maximum heart rate")
    max_max: float | None = Field(None, description="Maximum maximum heart rate")
    min_min: float | None = Field(None, description="Minimum minimum heart rate")
    max_min: float | None = Field(None, description="Maximum minimum heart rate")
    sort_by: Literal["date", "avg", "max", "min"] | None = Field(
        "date", description="Sort field"
    )
    sort_order: Literal["asc", "desc"] | None = Field(
        "desc", description="Sort order"
    )
    limit: int | None = Field(
        20, ge=1, le=100, description="Number of results to return"
    )
    offset: int | None = Field(0, ge=0, description="Number of results to skip")


class HeartRateValue(BaseModel):
    """Heart rate value with unit."""

    value: float
    unit: str = "bpm"


class HeartRateDataResponse(BaseModel):
    """Individual heart rate data response model."""

    id: int
    workout_id: UUID
    date: str  # ISO 8601
    source: str | None = None
    units: str | None = None
    avg: HeartRateValue | None = None
    min: HeartRateValue | None = None
    max: HeartRateValue | None = None


class HeartRateRecoveryResponse(BaseModel):
    """Individual heart rate recovery response model."""

    id: int
    workout_id: UUID
    date: str  # ISO 8601
    source: str | None = None
    units: str | None = None
    avg: HeartRateValue | None = None
    min: HeartRateValue | None = None
    max: HeartRateValue | None = None


class HeartRateSummary(BaseModel):
    """Heart rate summary statistics."""

    total_records: int
    avg_heart_rate: float
    max_heart_rate: float
    min_heart_rate: float
    avg_recovery_rate: float
    max_recovery_rate: float
    min_recovery_rate: float


class HeartRateMeta(BaseModel):
    """Metadata for heart rate response."""

    requested_at: str  # ISO 8601
    filters: dict
    result_count: int
    date_range: dict


class HeartRateListResponse(BaseModel):
    """Response model for heart rate data list endpoint."""

    data: list[HeartRateDataResponse]
    recovery_data: list[HeartRateRecoveryResponse]
    summary: HeartRateSummary
    meta: HeartRateMeta


# CRUD Schemas
class HeartRateDataCreate(BaseModel):
    """Schema for creating heart rate data."""
    
    user_id: UUID
    workout_id: UUID
    date: datetime
    source: str | None = None
    units: str | None = None
    avg: Decimal | None = None
    min: Decimal | None = None
    max: Decimal | None = None


class HeartRateDataUpdate(BaseModel):
    """Schema for updating heart rate data."""
    
    date: datetime | None = None
    source: str | None = None
    units: str | None = None
    avg: Decimal | None = None
    min: Decimal | None = None
    max: Decimal | None = None


class HeartRateRecoveryCreate(BaseModel):
    """Schema for creating heart rate recovery data."""
    
    user_id: UUID
    workout_id: UUID
    date: datetime
    source: str | None = None
    units: str | None = None
    avg: Decimal | None = None
    min: Decimal | None = None
    max: Decimal | None = None


class HeartRateRecoveryUpdate(BaseModel):
    """Schema for updating heart rate recovery data."""
    
    date: datetime | None = None
    source: str | None = None
    units: str | None = None
    avg: Decimal | None = None
    min: Decimal | None = None
    max: Decimal | None = None
