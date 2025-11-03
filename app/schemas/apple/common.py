from __future__ import annotations

from datetime import datetime
from typing import Literal, Any
from uuid import UUID

from pydantic import BaseModel, Field


class BaseQueryParams(BaseModel):
    """Common query parameters used across both auto_export and healthkit."""
    
    start_date: str | None = Field(
        None, description="ISO 8601 format (e.g., '2023-12-01T00:00:00Z')"
    )
    end_date: str | None = Field(
        None, description="ISO 8601 format (e.g., '2023-12-31T23:59:59Z')"
    )
    limit: int | None = Field(
        20, ge=1, le=100, description="Number of results to return"
    )
    offset: int | None = Field(0, ge=0, description="Number of results to skip")
    sort_order: Literal["asc", "desc"] | None = Field(
        "desc", description="Sort order"
    )


class BaseResponse(BaseModel):
    """Common response fields."""
    
    id: UUID
    created_at: datetime
    updated_at: datetime


class RootJSON(BaseModel):
    """Root JSON schema for record imports."""
    data: dict[str, Any]
    
    
class DateRange(BaseModel):
    """Date range information."""

    start: str
    end: str
    duration_days: int