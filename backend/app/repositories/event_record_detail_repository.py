from typing import Literal
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.inspection import inspect

from app.database import DbSession
from app.models import (
    EventRecordDetail,
    SleepDetails,
    WorkoutDetails,
)
from app.repositories.repositories import CrudRepository
from app.schemas.event_record_detail import (
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

    @handle_exceptions
    @handle_duplicates
    def create(
        self,
        db_session: DbSession,
        creator: EventRecordDetailCreate,
        detail_type: DetailType = "workout",
    ) -> EventRecordDetail:
        """Create a detail record using the appropriate polymorphic model."""
        creation_data = creator.model_dump(exclude_none=True)

        if detail_type == "workout":
            detail = WorkoutDetails(**creation_data)
        elif detail_type == "sleep":
            detail = SleepDetails(**creation_data)
        else:
            raise ValueError(f"Unknown detail type: {detail_type}")

        db_session.add(detail)
        db_session.commit()
        db_session.refresh(detail)
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

        base_stmt = insert(EventRecordDetail).values(base_values).on_conflict_do_nothing(index_elements=["record_id"])
        db_session.execute(base_stmt)

        # Use appropriate model based on detail_type
        model = WorkoutDetails if detail_type == "workout" else SleepDetails

        valid_columns = set(inspect(model).columns.keys())

        # Build values for child table (workout_details or sleep_details)
        child_values = []
        for creator in creators:
            data = creator.model_dump()
            # Filter to keep only columns present in the target model
            filtered_data = {k: v for k, v in data.items() if k in valid_columns}
            child_values.append(filtered_data)

        if not child_values:
            return

        child_stmt = insert(model).values(child_values)

        # Upsert: Update fields if record exists (fixes NULLs if record was created empty)
        update_dict = {
            col_name: getattr(child_stmt.excluded, col_name) for col_name in valid_columns if col_name != "record_id"
        }

        child_stmt = child_stmt.on_conflict_do_update(index_elements=["record_id"], set_=update_dict)
        db_session.execute(child_stmt)
        # NOTE: Caller should commit - allows batching multiple operations

    def get_by_record_id(self, db_session: DbSession, record_id: UUID) -> EventRecordDetail | None:
        """Get detail by its associated event record ID."""
        return db_session.query(EventRecordDetail).filter(EventRecordDetail.record_id == record_id).one_or_none()
