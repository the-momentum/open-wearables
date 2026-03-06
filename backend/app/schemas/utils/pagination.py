from math import ceil
from typing import Generic, TypeVar

from pydantic import BaseModel, Field, computed_field, field_validator

from .metadata import TimeseriesMetadata


class Pagination(BaseModel):
    next_cursor: str | None = Field(
        None,
        description="Cursor to fetch next page, null if no more data",
        example="eyJpZCI6IjEyMzQ1Njc4OTAiLCJ0cyI6MTcwNDA2NzIwMH0",
    )
    previous_cursor: str | None = Field(None, description="Cursor to fetch previous page")
    has_more: bool = Field(..., description="Whether more data is available")
    total_count: int | None = Field(
        None,
        description="Total number of records matching the query",
        example=150,
    )


class PaginatedResponse[DataT](BaseModel):
    """Generic response model for paginated data with metadata.

    Can be used with any data type by specifying the type parameter:
    - PaginatedResponse[HeartRateSample]
    - PaginatedResponse[HeartRateSample | HrvSample | Spo2Sample]
    - PaginatedResponse[Workout]  # for other endpoints
    """

    data: list[DataT]
    pagination: Pagination
    metadata: TimeseriesMetadata


# Kept for compatibility for now, may be up to refactor
T = TypeVar("T")


class OldPaginatedResponse(BaseModel, Generic[T]):
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
