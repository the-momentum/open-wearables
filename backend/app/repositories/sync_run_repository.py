from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import selectinload

from app.database import DbSession
from app.models import SyncRun, SyncRunDataType
from app.schemas.sync_status import DataTypeOutcome, SyncRunWrite, SyncScope, SyncStatus


class SyncRunRepository:
    """Durable storage for sync runs and their per-data-type outcomes.

    Rows are keyed by run_key, the same identifier the SSE stream and outgoing webhooks
    use as run_id, so an event stream can be joined to its stored run. The first event of
    a run inserts the row, later events update it in place.
    """

    def upsert_run(self, db_session: DbSession, run: SyncRunWrite) -> UUID:
        """Insert or update the run, returning its id.

        started_at is insert-only; requested_* fill in while empty, since the window is
        often not known until after the run has opened.
        """
        stmt = insert(SyncRun).values(id=uuid4(), **run.model_dump())
        stmt = stmt.on_conflict_do_update(
            index_elements=["run_key"],
            set_={
                "status": stmt.excluded.status,
                "requested_start": func.coalesce(SyncRun.requested_start, stmt.excluded.requested_start),
                "requested_end": func.coalesce(SyncRun.requested_end, stmt.excluded.requested_end),
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

    def upsert_data_types(
        self,
        db_session: DbSession,
        *,
        run_id: UUID,
        outcomes: list[DataTypeOutcome],
        updated_at: datetime,
    ) -> None:
        """Record the outcome of each data type within a run, in one transaction.

        Covered range widens rather than being replaced, so several batches of the same
        type accumulate into one span. attempt counts how many times the type reported in,
        which for an SDK export is once per batch plus once for its end event.
        """
        for outcome in outcomes:
            self._upsert_data_type(db_session, run_id=run_id, outcome=outcome, updated_at=updated_at)
        db_session.commit()

    def _upsert_data_type(
        self,
        db_session: DbSession,
        *,
        run_id: UUID,
        outcome: DataTypeOutcome,
        updated_at: datetime,
    ) -> None:
        stmt = insert(SyncRunDataType).values(
            run_id=run_id,
            attempt=1,
            updated_at=updated_at,
            **outcome.model_dump(),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["run_id", "data_type"],
            set_={
                "status": stmt.excluded.status,
                # Only the log end event knows the provider's own name for the type.
                "native_type": func.coalesce(stmt.excluded.native_type, SyncRunDataType.native_type),
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

    def find_stale(self, db_session: DbSession, cutoff: datetime) -> list[str]:
        """Keys of runs still in progress since before the cutoff.

        Age alone does not prove a run is dead, so the caller checks liveness before
        closing anything.
        """
        stmt = select(SyncRun.run_key).where(
            SyncRun.status == SyncStatus.IN_PROGRESS,
            SyncRun.started_at < cutoff,
        )
        return list(db_session.scalars(stmt).all())

    def close_as_stale(self, db_session: DbSession, run_keys: list[str], ended_at: datetime) -> list[str]:
        """Close the named runs as stale, returning the keys that actually changed.

        Stale is not failed: we never heard what happened. ended_at is when we gave up,
        not when it really stopped. The in_progress check is repeated because a run can
        report its outcome between being picked as a candidate and this update.
        """
        if not run_keys:
            return []

        stmt = (
            update(SyncRun)
            .where(SyncRun.run_key.in_(run_keys), SyncRun.status == SyncStatus.IN_PROGRESS)
            .values(status=SyncStatus.STALE, ended_at=ended_at, updated_at=ended_at)
            .returning(SyncRun.run_key)
        )
        closed = list(db_session.scalars(stmt).all())
        db_session.commit()
        return closed

    def get_by_run_key(self, db_session: DbSession, run_key: str) -> SyncRun | None:
        return db_session.execute(select(SyncRun).where(SyncRun.run_key == run_key)).scalar_one_or_none()

    def get_with_data_types(self, db_session: DbSession, run_key: str) -> SyncRun | None:
        stmt = select(SyncRun).where(SyncRun.run_key == run_key).options(selectinload(SyncRun.data_types))
        return db_session.execute(stmt).scalar_one_or_none()

    def list_for_user(
        self,
        db_session: DbSession,
        user_id: UUID,
        *,
        limit: int = 20,
        scope: SyncScope | None = None,
        since: datetime | None = None,
    ) -> list[SyncRun]:
        stmt = select(SyncRun).where(SyncRun.user_id == user_id).order_by(SyncRun.started_at.desc()).limit(limit)
        if scope is not None:
            stmt = stmt.where(SyncRun.scope == scope)
        if since is not None:
            stmt = stmt.where(SyncRun.started_at >= since)
        return list(db_session.execute(stmt).scalars().unique().all())


sync_run_repository = SyncRunRepository()
