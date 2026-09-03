from datetime import datetime
from uuid import UUID

from sqlalchemy import Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import BaseDbModel
from app.mappings import PrimaryKey, str_32, str_50, str_64


class SDKSyncRun(BaseDbModel):
    """Durable whole-run manifest for a streaming mobile SDK sync."""

    __tablename__ = "sdk_sync_run"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", "client_sync_id", name="uq_sdk_sync_run_client"),
        Index("ix_sdk_sync_run_status_updated", "status", "updated_at"),
    )

    id: Mapped[PrimaryKey[UUID]]
    user_id: Mapped[UUID] = mapped_column(index=True)
    provider: Mapped[str_50]
    client_sync_id: Mapped[str_64]
    status: Mapped[str_32]
    expected_chunks: Mapped[int | None]
    received_chunks: Mapped[int]
    processed_chunks: Mapped[int]
    received_items: Mapped[int]
    processed_items: Mapped[int]
    received_sleep_items: Mapped[int]
    declared_total_items: Mapped[int | None]
    started_at: Mapped[datetime | None]
    completed_at: Mapped[datetime | None]
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class SDKSyncChunk(BaseDbModel):
    """Idempotency and completion evidence for one SDK upload request."""

    __tablename__ = "sdk_sync_chunk"
    __table_args__ = (
        UniqueConstraint("run_id", "chunk_index", name="uq_sdk_sync_chunk_index"),
        Index("ix_sdk_sync_chunk_run_status", "run_id", "status"),
    )

    id: Mapped[PrimaryKey[UUID]]
    run_id: Mapped[UUID] = mapped_column(index=True)
    batch_id: Mapped[str_64] = mapped_column(unique=True)
    chunk_index: Mapped[int]
    payload_sha256: Mapped[str] = mapped_column(String(64))
    item_count: Mapped[int]
    processed_items: Mapped[int | None]
    status: Mapped[str_32]
    processed_at: Mapped[datetime | None]


__all__ = ["SDKSyncChunk", "SDKSyncRun"]
