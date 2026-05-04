"""Schemas for sync status events streamed via SSE.

A sync status event represents a state transition during a data
synchronization run for a user. Events are produced by Celery tasks
(pull syncs, Garmin backfill, SDK uploads) and webhook handlers, and
distributed to clients via Server-Sent Events (SSE).
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class SyncSource(StrEnum):
    """How the sync was initiated / what transport delivers data."""

    PULL = "pull"  # REST polling (sync_vendor_data)
    WEBHOOK = "webhook"  # Push delivery from provider
    SDK = "sdk"  # Mobile SDK upload (Apple HealthKit, Samsung Health, ...)
    BACKFILL = "backfill"  # Garmin webhook-based historical backfill
    XML_IMPORT = "xml_import"  # Apple Health XML upload


class SyncStage(StrEnum):
    """Coarse-grained stage label for a sync run."""

    QUEUED = "queued"
    STARTED = "started"
    FETCHING = "fetching"
    PROCESSING = "processing"
    SAVING = "saving"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SyncStatus(StrEnum):
    """Overall outcome state for the run."""

    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SyncStatusEvent(BaseModel):
    """A single status update for a sync run."""

    model_config = ConfigDict(use_enum_values=True)

    event_id: UUID = Field(default_factory=uuid4, description="Unique ID for this event.")
    run_id: str = Field(description="Identifier shared by all events of the same sync run.")
    user_id: UUID
    provider: str = Field(description="Provider slug (e.g. 'garmin', 'apple', 'whoop').")
    source: SyncSource
    stage: SyncStage
    status: SyncStatus
    message: str | None = None
    progress: float | None = Field(default=None, ge=0.0, le=1.0, description="Optional 0..1 progress.")
    items_processed: int | None = Field(default=None, ge=0)
    items_total: int | None = Field(default=None, ge=0)
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    ended_at: datetime | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SyncRunSummary(BaseModel):
    """Latest known status for a sync run, derived from the event stream."""

    run_id: str
    user_id: UUID
    provider: str
    source: str
    stage: str
    status: str
    message: str | None = None
    progress: float | None = None
    items_processed: int | None = None
    items_total: int | None = None
    error: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    last_update: datetime
