from datetime import datetime
from uuid import UUID

from sqlalchemy import Index, text
from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import FKUser, PrimaryKey, Unique, int_zero, json_object, str_32, str_64
from app.schemas.sync_status import SyncScope, SyncSource, SyncStatus


class SyncRun(BaseDbModel):
    """One data sync run, with the outcome of each data type it covered.

    ``data_types`` maps a canonical data type (SeriesType slug, or DetailType for
    session data) to its outcome, so a run carries its own breakdown without a
    child table::

        {"heart_rate": {"status": "success", "records": 41230, "started_at": ...,
                        "covered_start": ..., "native_type": "HKQuantityTypeIdentifierHeartRate"},
         "sleep":      {"status": "failed", "error": "authorization_denied", ...}}

    Per-type updates are applied with a single ``jsonb_set`` so concurrent writes
    for different types cannot clobber each other. ``meta`` holds provider-specific
    context that is only ever read by a human (Garmin's window matrix, SDK version
    and device state, pull params) — anything the code branches on gets a column.
    """

    __tablename__ = "sync_run"
    __table_args__ = (
        # Equality on user_id + ORDER BY started_at DESC scans this backwards.
        Index("ix_sync_run_user_started_at", "user_id", "started_at"),
        Index("ix_sync_run_provider_status", "provider", "status"),
        Index("ix_sync_run_data_types", "data_types", postgresql_using="gin"),
        # Feeds the stale-run sweeper, which only ever looks at unfinished runs.
        Index(
            "ix_sync_run_in_progress",
            "started_at",
            postgresql_where=text("status = 'in_progress'"),
        ),
    )

    id: Mapped[PrimaryKey[UUID]]
    # Shared with the SSE stream and outgoing webhooks (``run_id`` there).
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
    # from the per-type entries in ``data_types``.
    requested_start: Mapped[datetime | None]
    requested_end: Mapped[datetime | None]

    started_at: Mapped[datetime]
    ended_at: Mapped[datetime | None]

    items_inserted: Mapped[int_zero]
    items_updated: Mapped[int_zero]
    error: Mapped[str | None]

    data_types: Mapped[json_object | None]
    meta: Mapped[json_object | None]

    updated_at: Mapped[datetime]
