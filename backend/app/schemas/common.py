from datetime import datetime
from math import ceil
from typing import Any, Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field, computed_field, field_validator

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""

    items: list[T]
    total: int = Field(ge=0, description="Total number of items matching the query")
    page: int = Field(ge=1, description="Current page number (1-based)")
    limit: int = Field(gt=0, description="Number of items per page")

    @field_validator("limit")
    @classmethod
    def limit_must_be_positive(cls, v: int) -> int:
        """Ensure limit is positive to prevent division by zero in pages calculation."""
        if v <= 0:
            raise ValueError("limit must be greater than 0")
        return v

    @computed_field
    @property
    def pages(self) -> int:
        """Total number of pages."""
        return ceil(self.total / self.limit)

    @computed_field
    @property
    def has_next(self) -> bool:
        """Whether there is a next page."""
        return self.page < self.pages

    @computed_field
    @property
    def has_prev(self) -> bool:
        """Whether there is a previous page."""
        return self.page > 1


class BaseQueryParams(BaseModel):
    """Common query parameters used across both auto_export and healthkit."""

    start_date: str | None = Field(None, description="ISO 8601 format (e.g., '2023-12-01T00:00:00Z')")
    end_date: str | None = Field(None, description="ISO 8601 format (e.g., '2023-12-31T23:59:59Z')")
    limit: int | None = Field(20, ge=1, le=100, description="Number of results to return")
    offset: int | None = Field(0, ge=0, description="Number of results to skip")
    sort_order: Literal["asc", "desc"] | None = Field("desc", description="Sort order")


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
