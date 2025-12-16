from datetime import datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field
from pydantic.generics import GenericModel


class DataSource(BaseModel):
    provider: str = Field(..., example="apple_health")
    device: str | None = Field(None, example="Apple Watch Series 9")


class TimeseriesMetadata(BaseModel):
    resolution: Literal["raw", "1min", "5min", "15min", "1hour"] | None = None
    sample_count: int | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None


class Pagination(BaseModel):
    next_cursor: str | None = Field(
        None,
        description="Cursor to fetch next page, null if no more data",
        example="eyJpZCI6IjEyMzQ1Njc4OTAiLCJ0cyI6MTcwNDA2NzIwMH0",
    )
    previous_cursor: str | None = Field(None, description="Cursor to fetch previous page")
    has_more: bool = Field(..., description="Whether more data is available")


class ErrorDetails(BaseModel):
    code: str
    message: str
    details: dict | None = None


# Type variable for generic paginated data
DataT = TypeVar("DataT")


class PaginatedResponse(GenericModel, Generic[DataT]):
    """Generic response model for paginated data with metadata.

    Can be used with any data type by specifying the type parameter:
    - PaginatedResponse[HeartRateSample]
    - PaginatedResponse[Union[HeartRateSample, HrvSample, Spo2Sample]]
    - PaginatedResponse[Workout]  # for other endpoints
    """

    data: list[DataT]
    pagination: Pagination
    metadata: TimeseriesMetadata
