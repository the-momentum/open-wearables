from __future__ import annotations

import hashlib
from dataclasses import dataclass
from uuid import UUID

from app.database import DbSession
from app.models.sdk_sync_run import SDKSyncRun
from app.repositories.sdk_sync_run_repository import sdk_sync_run_repository


@dataclass(frozen=True, slots=True)
class AcceptedSDKSyncChunk:
    batch_id: str
    duplicate: bool
    status: str


class SDKSyncRunService:
    """Validate and coordinate whole-run completion for streaming SDK uploads."""

    def accept_chunk(
        self,
        db: DbSession,
        *,
        user_id: str,
        provider: str,
        client_sync_id: str,
        chunk_index: int,
        is_final: bool,
        declared_total_items: int | None,
        item_count: int,
        sleep_item_count: int,
        payload: bytes,
        batch_id: str,
    ) -> AcceptedSDKSyncChunk:
        if not client_sync_id or len(client_sync_id) > 64:
            raise ValueError("client sync id must contain 1-64 characters")
        if chunk_index < 0:
            raise ValueError("sync chunk index must be non-negative")
        if is_final and declared_total_items is None:
            raise ValueError("final sync marker requires total item count")
        if declared_total_items is not None and declared_total_items < 0:
            raise ValueError("total item count must be non-negative")
        if sleep_item_count < 0 or sleep_item_count > item_count:
            raise ValueError("sleep item count must be between zero and item count")
        manifest_envelope = b"\0".join(
            (
                str(chunk_index).encode(),
                str(is_final).encode(),
                str(declared_total_items).encode(),
                str(item_count).encode(),
                payload,
            )
        )
        _, chunk, duplicate = sdk_sync_run_repository.accept_chunk(
            db,
            user_id=UUID(user_id),
            provider=provider,
            client_sync_id=client_sync_id,
            chunk_index=chunk_index,
            is_final=is_final,
            declared_total_items=declared_total_items,
            item_count=item_count,
            sleep_item_count=sleep_item_count,
            payload_sha256=hashlib.sha256(manifest_envelope).hexdigest(),
            batch_id=batch_id,
        )
        return AcceptedSDKSyncChunk(
            batch_id=chunk.batch_id,
            duplicate=duplicate,
            status=chunk.status,
        )

    def mark_started(self, db: DbSession, *, batch_id: str) -> tuple[SDKSyncRun, bool]:
        return sdk_sync_run_repository.mark_started(db, batch_id=batch_id)

    def mark_processed(
        self,
        db: DbSession,
        *,
        batch_id: str,
        processed_items: int,
    ) -> tuple[SDKSyncRun, bool, bool]:
        return sdk_sync_run_repository.mark_processed(
            db,
            batch_id=batch_id,
            processed_items=processed_items,
        )

    def mark_failed(self, db: DbSession, *, batch_id: str) -> tuple[SDKSyncRun, bool]:
        return sdk_sync_run_repository.mark_failed(db, batch_id=batch_id)


sdk_sync_run_service = SDKSyncRunService()

__all__ = ["AcceptedSDKSyncChunk", "SDKSyncRunService", "sdk_sync_run_service"]
