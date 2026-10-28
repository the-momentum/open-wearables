from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.sync_status import SyncStatus


class ProviderSyncResult(BaseModel):
    success: bool
    params: dict[str, Any]


class SyncVendorDataResult(BaseModel):
    user_id: UUID | str
    start_date: str | None = None
    end_date: str | None = None
    providers_synced: dict[str, ProviderSyncResult] = {}
    errors: dict[str, str] = {}
    message: str | None = None


class SyncAllUsersResult(BaseModel):
    users_for_sync: int


class Sync247TaskSummary(BaseModel):
    """One provider fetch task of a 24/7 sync. Counters mean what they do in sync.data_type events."""

    status: SyncStatus
    items_inserted: int | None = Field(description="New rows, when the write path reports the split")
    items_updated: int | None = Field(description="Rows refreshed in place, when the write path reports the split")
    items_reported: int | None = Field(description="Rows written, when only a total is known")
    items_skipped: int = Field(description="Records deliberately not stored, such as duplicates")
    truncated: bool = Field(description="The fetch stopped early, so the window is incomplete")
    error_code: str | None = Field(
        description=(
            "The provider's HTTP status (http_404) or the error type (ProviderReauthorizationRequiredError) "
            "of the first failure"
        )
    )


class Sync247Summary(BaseModel):
    """A 24/7 sync: totals over its provider fetch tasks, and each task."""

    status: SyncStatus
    items_inserted: int | None
    items_updated: int | None
    items_reported: int | None
    error_code: str | None = Field(None, description="Set when the whole sync failed before any task ran")
    tasks: dict[str, Sync247TaskSummary]


class SyncDetails(BaseModel):
    workouts: int | None = Field(None, description="Workouts saved, when workouts were synced")
    data_247: Sync247Summary | None = None


class SyncResponse(BaseModel):
    """A synchronous sync's outcome."""

    success: bool
    details: SyncDetails


class SyncQueuedResponse(BaseModel):
    """A sync queued to run in the background."""

    success: bool
    is_async: bool = Field(serialization_alias="async")
    task_id: str
    message: str
