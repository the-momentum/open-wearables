from typing import Any, cast
from uuid import UUID

from sqlalchemy import Table, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from app.database import DbSession
from app.models import (
    DETAIL_MODELS,
    DetailType,
    EventRecordDetail,
    WorkoutDetails,
)
from app.repositories.repositories import CrudRepository
from app.schemas.model_crud.activities import (
    EventRecordDetailCreate,
    EventRecordDetailUpdate,
)
from app.utils.duplicates import handle_duplicates
from app.utils.exceptions import handle_exceptions


class EventRecordDetailRepository(
    CrudRepository[EventRecordDetail, EventRecordDetailCreate, EventRecordDetailUpdate],
):
    def __init__(self, model: type[EventRecordDetail]):
        super().__init__(model)

    def _build_detail(self, creator: EventRecordDetailCreate, detail_type: DetailType) -> EventRecordDetail:
        """Construct the concrete detail ORM object without touching the session."""
        model = DETAIL_MODELS.get(detail_type)
        if model is None:
            raise ValueError(f"Unknown detail type: {detail_type}")
        creation_data = creator.model_dump(exclude_none=True)
        if detail_type == "sleep" and creator.sleep_stages:
            # sleep_stages contains datetime fields that JSONB cannot serialize directly;
            # use Pydantic's JSON mode to convert datetimes to ISO strings.
            creation_data["sleep_stages"] = [s.model_dump(mode="json") for s in creator.sleep_stages]
        return model(**creation_data)

    @handle_exceptions
    @handle_duplicates
    def create(
        self,
        db_session: DbSession,
        creator: EventRecordDetailCreate,
        detail_type: DetailType = "workout",
    ) -> EventRecordDetail:
        """Create a detail record using the appropriate polymorphic model."""
        detail = self._build_detail(creator, detail_type)
        db_session.add(detail)
        db_session.commit()
        db_session.refresh(detail)
        return detail

    def create_and_flush(
        self,
        db_session: DbSession,
        creator: EventRecordDetailCreate,
        detail_type: DetailType = "workout",
    ) -> EventRecordDetail:
        """Like create() but flushes instead of committing; caller is responsible for the commit.

        Uses a savepoint for IntegrityError handling so a conflict rolls back only
        the INSERT and leaves the outer transaction intact.
        """
        detail = self._build_detail(creator, detail_type)
        nested = db_session.begin_nested()
        try:
            db_session.add(detail)
            db_session.flush()
            nested.commit()
            return detail
        except IntegrityError:
            nested.rollback()
            if existing := self.get_by_record_id(db_session, creator.record_id, detail_type):
                return existing
            raise

    @handle_exceptions
    def bulk_create(
        self,
        db_session: DbSession,
        creators: list[EventRecordDetailCreate],
        detail_type: DetailType = "workout",
    ) -> None:
        """Bulk create detail records using batch insert."""
        if not creators:
            return

        model = DETAIL_MODELS.get(detail_type)
        if model is None:
            raise ValueError(f"Unknown detail type: {detail_type}")

        child_table = cast(Table, model.__table__)
        valid_columns = set(child_table.columns.keys())

        child_values = []
        for creator in creators:
            data = creator.model_dump()
            if detail_type == "sleep" and data.get("sleep_stages"):
                data["sleep_stages"] = [s.model_dump(mode="json") for s in creator.sleep_stages]  # ty:ignore[not-iterable]
            filtered_data = {k: v for k, v in data.items() if k in valid_columns}
            child_values.append(filtered_data)

        if not child_values:
            return

        child_stmt = insert(child_table).values(child_values)
        # record_id is the conflict key; created_at is an immutable audit column and
        # must not be reset to now() when an existing row is re-synced.
        immutable_on_upsert = {"record_id", "created_at"}
        update_dict = {
            col_name: child_stmt.excluded[col_name] for col_name in valid_columns if col_name not in immutable_on_upsert
        }
        child_stmt = child_stmt.on_conflict_do_update(index_elements=["record_id"], set_=update_dict)
        db_session.execute(child_stmt)
        # NOTE: Caller should commit - allows batching multiple operations

    def get_by_record_id(
        self,
        db_session: DbSession,
        record_id: UUID,
        detail_type: DetailType | None = None,
    ) -> EventRecordDetail | None:
        """Get detail by its associated event record ID.

        Pass detail_type when known to avoid querying all three tables.
        """
        if detail_type is not None:
            model = DETAIL_MODELS[detail_type]
            return db_session.query(model).filter(model.record_id == record_id).one_or_none()
        for model in DETAIL_MODELS.values():
            result = db_session.query(model).filter(model.record_id == record_id).one_or_none()
            if result is not None:
                return result
        return None

    def delete_by_record_id(
        self,
        db_session: DbSession,
        record_id: UUID,
        detail_type: DetailType | None = None,
    ) -> None:
        """Delete the detail row for a given record, flushing immediately so the
        slot is free for a replacement insert in the same transaction."""
        detail = self.get_by_record_id(db_session, record_id, detail_type)
        if detail is not None:
            db_session.delete(detail)
            db_session.flush()

    def update_workout_fields(
        self,
        db_session: DbSession,
        record_id: UUID,
        fields: dict[str, Any],
    ) -> None:
        """Patch one or more columns on the workout_details row for the given record.

        Intended for JSONB fields (segments, hr_zones, power_zones) that are
        written separately from the initial bulk insert.
        NOTE: Caller is responsible for committing or flushing the transaction.
        """
        db_session.execute(update(WorkoutDetails).where(WorkoutDetails.record_id == record_id).values(**fields))
