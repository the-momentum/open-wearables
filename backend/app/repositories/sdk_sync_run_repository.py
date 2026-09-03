from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import func

from app.database import DbSession
from app.models.sdk_sync_run import SDKSyncChunk, SDKSyncRun


class SDKSyncRunRepository:
    """Atomic persistence operations for SDK whole-run manifests."""

    def accept_chunk(
        self,
        db: DbSession,
        *,
        user_id: UUID,
        provider: str,
        client_sync_id: str,
        chunk_index: int,
        is_final: bool,
        declared_total_items: int | None,
        item_count: int,
        sleep_item_count: int,
        payload_sha256: str,
        batch_id: str,
    ) -> tuple[SDKSyncRun, SDKSyncChunk, bool]:
        run = (
            db.query(SDKSyncRun)
            .filter(
                SDKSyncRun.user_id == user_id,
                SDKSyncRun.provider == provider,
                SDKSyncRun.client_sync_id == client_sync_id,
            )
            .with_for_update()
            .one_or_none()
        )
        if run is None:
            run = SDKSyncRun(
                id=uuid4(),
                user_id=user_id,
                provider=provider,
                client_sync_id=client_sync_id,
                status="accepting",
                expected_chunks=None,
                received_chunks=0,
                processed_chunks=0,
                received_items=0,
                processed_items=0,
                received_sleep_items=0,
                declared_total_items=None,
                started_at=None,
                completed_at=None,
            )
            db.add(run)
            db.flush()

        existing = (
            db.query(SDKSyncChunk)
            .filter(
                SDKSyncChunk.run_id == run.id,
                SDKSyncChunk.chunk_index == chunk_index,
            )
            .one_or_none()
        )
        if existing is not None:
            if existing.payload_sha256 != payload_sha256:
                raise ValueError("sync chunk index was reused with different content")
            return run, existing, True
        if run.status in ("completed", "failed"):
            raise ValueError(f"sync run is already {run.status}")
        if run.expected_chunks is not None and chunk_index >= run.expected_chunks:
            raise ValueError("sync chunk arrived after the final marker")
        if is_final:
            expected_chunks = chunk_index + 1
            prior_after_final = (
                db.query(func.count(SDKSyncChunk.id))
                .filter(
                    SDKSyncChunk.run_id == run.id,
                    SDKSyncChunk.chunk_index >= expected_chunks,
                )
                .scalar()
                or 0
            )
            if prior_after_final:
                raise ValueError("final marker precedes an already accepted chunk")
            if run.expected_chunks not in (None, expected_chunks):
                raise ValueError("conflicting final marker")
            run.expected_chunks = expected_chunks
            run.declared_total_items = declared_total_items

        chunk = SDKSyncChunk(
            id=uuid4(),
            run_id=run.id,
            batch_id=batch_id,
            chunk_index=chunk_index,
            payload_sha256=payload_sha256,
            item_count=item_count,
            processed_items=None,
            status="accepted",
            processed_at=None,
        )
        db.add(chunk)
        run.received_chunks += 1
        run.received_items += item_count
        run.received_sleep_items += sleep_item_count
        run.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(run)
        db.refresh(chunk)
        return run, chunk, False

    def mark_started(self, db: DbSession, *, batch_id: str) -> tuple[SDKSyncRun, bool]:
        run = self._run_for_batch(db, batch_id=batch_id, lock=True)
        should_emit = run.started_at is None
        if should_emit:
            now = datetime.now(timezone.utc)
            run.started_at = now
            run.updated_at = now
            db.commit()
            db.refresh(run)
        return run, should_emit

    def mark_processed(
        self,
        db: DbSession,
        *,
        batch_id: str,
        processed_items: int,
    ) -> tuple[SDKSyncRun, bool, bool]:
        chunk = db.query(SDKSyncChunk).filter(SDKSyncChunk.batch_id == batch_id).with_for_update().one()
        run = db.query(SDKSyncRun).filter(SDKSyncRun.id == chunk.run_id).with_for_update().one()
        if chunk.status == "processed":
            return run, False, run.status == "failed"

        now = datetime.now(timezone.utc)
        chunk.status = "processed"
        chunk.processed_items = processed_items
        chunk.processed_at = now
        run.processed_chunks += 1
        run.processed_items += processed_items
        run.updated_at = now

        is_terminal = run.expected_chunks is not None and run.processed_chunks == run.expected_chunks
        count_mismatch = False
        if is_terminal:
            count_mismatch = (
                run.declared_total_items is None
                or run.declared_total_items != run.received_items
                or run.declared_total_items != run.processed_items
            )
            run.status = "failed" if count_mismatch else "completed"
            run.completed_at = now
        db.commit()
        db.refresh(run)
        return run, is_terminal, count_mismatch

    def mark_failed(self, db: DbSession, *, batch_id: str) -> tuple[SDKSyncRun, bool]:
        run = self._run_for_batch(db, batch_id=batch_id, lock=True)
        should_emit = run.status != "failed"
        if should_emit:
            now = datetime.now(timezone.utc)
            run.status = "failed"
            run.completed_at = now
            run.updated_at = now
            db.commit()
            db.refresh(run)
        return run, should_emit

    @staticmethod
    def _run_for_batch(db: DbSession, *, batch_id: str, lock: bool) -> SDKSyncRun:
        query = (
            db.query(SDKSyncRun)
            .join(SDKSyncChunk, SDKSyncChunk.run_id == SDKSyncRun.id)
            .filter(SDKSyncChunk.batch_id == batch_id)
        )
        if lock:
            query = query.with_for_update()
        return query.one()


sdk_sync_run_repository = SDKSyncRunRepository()

__all__ = ["SDKSyncRunRepository", "sdk_sync_run_repository"]
