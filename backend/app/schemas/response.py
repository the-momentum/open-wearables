from pydantic import BaseModel, Field


class UploadDataResponse(BaseModel):
    """Response schema for data upload/sync operations.

    Returned when health data is queued for asynchronous processing via Celery.
    The actual import happens in the background - this response indicates the task was queued successfully.
    """

    status_code: int = Field(..., description="HTTP status code (typically 202 for async operations)")
    response: str = Field(..., description="Human-readable response message")
    user_id: str | None = Field(None, description="User ID associated with the import operation")
