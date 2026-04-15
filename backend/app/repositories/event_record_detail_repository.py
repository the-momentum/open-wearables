from typing import Literal, cast
from uuid import UUID

from sqlalchemy import Table
from sqlalchemy.dialects.postgresql import insert

from app.database import DbSession
from app.models import (
    EventRecordDetail,
    SleepDetails,
    WorkoutDetails,
)
from app.repositories.repositories import CrudRepository
from app.schemas.model_crud.activities import (
    EventRecordDetailCreate,
    EventRecordDetailUpdate,
)
from app.utils.duplicates import handle_duplicates
from app.utils.exceptions import handle_exceptions

DetailType = Literal["workout", "sleep"]


class EventRecordDetailRepository(
    CrudRepository[EventRecordDetail, EventRecordDetailCreate, EventRecordDetailUpdate],
):
    def __init__(self, model: type[EventRecordDetail]):
        super().__init__(model)

    def _build_detail(self, creator: EventRecordDetailCreate, detail_type: DetailType) -> EventRecordDetail:
        """Construct the polymorphic ORM object without touching the session."""
        creation_data = creator.model_dump(exclude_none=True)
        if detail_type == "workout":
            return cast(EventRecordDetail, WorkoutDetails(**creation_data))
        if detail_type == "sleep":
            # sleep_stages contains datetime fields that JSONB cannot serialize directly;
            # use Pydantic's JSON mode to convert datetimes to ISO strings.
            if creator.sleep_stages:
                creation_data["sleep_stages"] = [s.model_dump(mode="json") for s in creator.sleep_stages]
            return cast(EventRecordDetail, SleepDetails(**creation_data))
        raise ValueError(f"Unknown detail type: {detail_type}")

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
        """Like create() but flushes instead of committing; caller is responsible for the commit."""
        detail = self._build_detail(creator, detail_type)
        db_session.add(detail)
        db_session.flush()
        return detail

    @handle_exceptions
    def bulk_create(
        self,
        db_session: DbSession,
        creators: list[EventRecordDetailCreate],
        detail_type: DetailType = "workout",
    ) -> None:
        """Bulk create detail records using batch insert.

        For joined table inheritance, we need to insert into both the base table
        (event_record_detail) and the child table (workout_details/sleep_details).
        """
        if not creators:
            return

        # Build values for base table (event_record_detail)
        base_values = []
        for creator in creators:
            base_values.append(
                {
                    "record_id": creator.record_id,
                    "detail_type": detail_type,
                }
            )

        if not base_values:
            return

        # Use __table__ for raw INSERT to avoid polymorphic mapper issues
        base_table = cast(Table, EventRecordDetail.__table__)
        base_stmt = insert(base_table).values(base_values).on_conflict_do_nothing(index_elements=["record_id"])
        db_session.execute(base_stmt)

        # Use appropriate model based on detail_type
        model = WorkoutDetails if detail_type == "workout" else SleepDetails

        # Get columns from the actual child TABLE (not mapper which includes inherited columns)
        child_table = cast(Table, model.__table__)
        valid_columns = set(child_table.columns.keys())

        # Build values for child table (workout_details or sleep_details)
        child_values = []
        for creator in creators:
            data = creator.model_dump()
            # Serialize sleep_stages datetimes to ISO strings for JSONB storage
            if detail_type == "sleep" and data.get("sleep_stages"):
                data["sleep_stages"] = [s.model_dump(mode="json") for s in creator.sleep_stages]  # type: ignore[union-attr]
            # Filter to keep only columns present in the target model
            filtered_data = {k: v for k, v in data.items() if k in valid_columns}
            child_values.append(filtered_data)

        if not child_values:
            return

        # Use __table__ for raw INSERT to avoid polymorphic mapper issues
        child_stmt = insert(child_table).values(child_values)

        # Upsert: Update fields if record exists (fixes NULLs if record was created empty)
        update_dict = {col_name: child_stmt.excluded[col_name] for col_name in valid_columns if col_name != "record_id"}

        child_stmt = child_stmt.on_conflict_do_update(index_elements=["record_id"], set_=update_dict)
        db_session.execute(child_stmt)
        # NOTE: Caller should commit - allows batching multiple operations

    def get_by_record_id(self, db_session: DbSession, record_id: UUID) -> EventRecordDetail | None:
        """Get detail by its associated event record ID."""
        return db_session.query(EventRecordDetail).filter(EventRecordDetail.record_id == record_id).one_or_none()

    def delete_by_record_id(self, db_session: DbSession, record_id: UUID) -> None:
        """Delete the detail row for a given record, flushing immediately so the
        slot is free for a replacement insert in the same transaction."""
        detail = self.get_by_record_id(db_session, record_id)
        if detail is not None:
            db_session.delete(detail)
            db_session.flush()
