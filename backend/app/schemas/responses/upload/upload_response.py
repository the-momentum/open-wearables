from pydantic import BaseModel, Field


class UploadDataResponse(BaseModel):
    """Response schema for data upload/sync operations.

    Returned when health data is queued for asynchronous processing via Celery.
    The actual import happens in the background - this response indicates the task was queued successfully.
    """

    status_code: int = Field(..., description="HTTP status code (typically 202 for async operations)")
    response: str = Field(..., description="Human-readable response message")
    user_id: str | None = Field(None, description="User ID associated with the import operation")
    dropped_count: int = Field(0, description="Number of individual records dropped by per-record validation")
    records_saved: int = Field(0, description="Time-series samples saved")
    records_inserted: int = Field(0, description="Time-series rows that did not exist before")
    records_updated: int = Field(0, description="Time-series rows refreshed in place")
    types: list[str] = Field(
        default_factory=list,
        description=(
            "Canonical SeriesType identifiers written by this batch (e.g. 'heart_rate'), "
            "sorted. Empty when the batch saved no time-series samples."
        ),
    )
    workouts_saved: int = Field(0, description="Workouts saved")
    sleep_saved: int = Field(0, description="Sleep records saved")
