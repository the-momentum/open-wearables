from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.database import DbSession
from app.models import SyncRun, SyncRunDataType
from app.schemas.sync_status import SyncScope, SyncSource, SyncStatus


class SyncRunRepository:
    """Durable storage for sync runs and their per-data-type outcomes.

    Rows are keyed by run_key, the same identifier the SSE stream and outgoing webhooks
    use as run_id, so an event stream can be joined to its stored run. The first event of
    a run inserts the row, later events update it in place.
    """

    def upsert_run(
        self,
        db_session: DbSession,
        *,
        run_key: str,
        user_id: UUID,
        provider: str,
        source: SyncSource,
        scope: SyncScope,
        status: SyncStatus,
        started_at: datetime,
        updated_at: datetime,
        ended_at: datetime | None = None,
        trace_id: str | None = None,
        requested_start: datetime | None = None,
        requested_end: datetime | None = None,
        items_inserted: int = 0,
        items_updated: int = 0,
        error: str | None = None,
        meta: dict | None = None,
    ) -> UUID:
        """Insert or update the run, returning its id.

        started_at and requested_* are only set on insert: they describe the run's
        intent, which later events must not overwrite.
        """
        stmt = insert(SyncRun).values(
            id=uuid4(),
            run_key=run_key,
            user_id=user_id,
            provider=provider,
            source=source,
            scope=scope,
            status=status,
            trace_id=trace_id,
            requested_start=requested_start,
            requested_end=requested_end,
            started_at=started_at,
            ended_at=ended_at,
            items_inserted=items_inserted,
            items_updated=items_updated,
            error=error,
            meta=meta,
            updated_at=updated_at,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["run_key"],
            set_={
                "status": stmt.excluded.status,
                "ended_at": stmt.excluded.ended_at,
                "items_inserted": stmt.excluded.items_inserted,
                "items_updated": stmt.excluded.items_updated,
                "error": stmt.excluded.error,
                "meta": stmt.excluded.meta,
                "updated_at": stmt.excluded.updated_at,
            },
        ).returning(SyncRun.id)
        run_id = db_session.execute(stmt).scalar_one()
        db_session.commit()
        return run_id

    def upsert_data_type(
        self,
        db_session: DbSession,
        *,
        run_id: UUID,
        data_type: str,
        kind: str,
        status: SyncStatus,
        updated_at: datetime,
        native_type: str | None = None,
        reported_records: int | None = None,
        items_inserted: int = 0,
        items_updated: int = 0,
        covered_start: datetime | None = None,
        covered_end: datetime | None = None,
        started_at: datetime | None = None,
        ended_at: datetime | None = None,
        duration_ms: int | None = None,
        error_code: str | None = None,
        error: str | None = None,
    ) -> None:
        """Record the outcome of one data type within a run.

        Covered range widens rather than being replaced, so several batches of the same
        type accumulate into one span. A retried type increments attempt.
        """
        stmt = insert(SyncRunDataType).values(
            run_id=run_id,
            data_type=data_type,
            kind=kind,
            status=status,
            native_type=native_type,
            reported_records=reported_records,
            items_inserted=items_inserted,
            items_updated=items_updated,
            covered_start=covered_start,
            covered_end=covered_end,
            started_at=started_at,
            ended_at=ended_at,
            duration_ms=duration_ms,
            error_code=error_code,
            error=error,
            attempt=1,
            updated_at=updated_at,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["run_id", "data_type"],
            set_={
                "status": stmt.excluded.status,
                "reported_records": func.coalesce(stmt.excluded.reported_records, SyncRunDataType.reported_records),
                "items_inserted": SyncRunDataType.items_inserted + stmt.excluded.items_inserted,
                "items_updated": SyncRunDataType.items_updated + stmt.excluded.items_updated,
                "covered_start": func.least(stmt.excluded.covered_start, SyncRunDataType.covered_start),
                "covered_end": func.greatest(stmt.excluded.covered_end, SyncRunDataType.covered_end),
                "ended_at": stmt.excluded.ended_at,
                "duration_ms": stmt.excluded.duration_ms,
                "error_code": stmt.excluded.error_code,
                "error": stmt.excluded.error,
                "attempt": SyncRunDataType.attempt + 1,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        db_session.execute(stmt)
        db_session.commit()

    def get_by_run_key(self, db_session: DbSession, run_key: str) -> SyncRun | None:
        return db_session.execute(select(SyncRun).where(SyncRun.run_key == run_key)).scalar_one_or_none()


sync_run_repository = SyncRunRepository()
