from datetime import datetime
from uuid import UUID

from sqlalchemy import Index, text
from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import FKUser, OneToMany, PrimaryKey, Unique, int_zero, json_object, str_32, str_64
from app.models.sync_run_data_type import SyncRunDataType
from app.schemas.sync_status import SyncScope, SyncSource, SyncStatus


class SyncRun(BaseDbModel):
    """One data sync run. The outcome of each data type it covered is a SyncRunDataType row.

    meta holds provider-specific context that is only ever read by a human (Garmin's
    window matrix, SDK version and device state, pull params) — anything the code
    branches on gets a column.
    """

    __tablename__ = "sync_run"
    __table_args__ = (
        # Equality on user_id + ORDER BY started_at DESC scans this backwards.
        Index("ix_sync_run_user_started_at", "user_id", "started_at"),
        Index("ix_sync_run_provider_status", "provider", "status"),
        # Feeds the stale-run sweeper, which only ever looks at unfinished runs.
        Index(
            "ix_sync_run_in_progress",
            "started_at",
            postgresql_where=text("status = 'in_progress'"),
        ),
    )

    id: Mapped[PrimaryKey[UUID]]
    # Shared with the SSE stream and outgoing webhooks (run_id there).
    run_key: Mapped[Unique[str_64]]
    # No separate index — ix_sync_run_user_started_at covers user_id as its prefix.
    user_id: Mapped[FKUser]
    # Free-form rather than ProviderName: this is an audit log, so an unexpected
    # slug must still be recorded rather than rejected on insert.
    provider: Mapped[str_64]

    source: Mapped[SyncSource]
    scope: Mapped[SyncScope]
    status: Mapped[SyncStatus]
    trace_id: Mapped[str_32 | None]

    # What we asked the provider for. The range we actually covered is derived
    # from the per-type rows.
    requested_start: Mapped[datetime | None]
    requested_end: Mapped[datetime | None]

    started_at: Mapped[datetime]
    ended_at: Mapped[datetime | None]

    items_inserted: Mapped[int_zero]
    items_updated: Mapped[int_zero]
    error: Mapped[str | None]

    meta: Mapped[json_object | None]

    data_types: Mapped[OneToMany[SyncRunDataType]]

    updated_at: Mapped[datetime]
