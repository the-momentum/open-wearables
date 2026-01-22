from typing import Literal
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert

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

    def bulk_create(
        self,
        db_session: DbSession,
        creators: list[EventRecordDetailCreate],
        detail_type: DetailType = "workout",
    ) -> list[EventRecordDetail]:
        """Bulk create detail records using the appropriate polymorphic model.

        For polymorphic inheritance, we need to insert into event_record_detail first,
        then into the specific table (workout_details or sleep_details).
        """
        if not creators:
            return []

        # First, insert into event_record_detail (base table) with just record_id and detail_type
        base_values_list = []
        detail_values_list = []

        for creator in creators:
            creation_data = creator.model_dump(exclude_none=True)
            record_id = creation_data.pop("record_id")

            # Base table insert
            base_values_list.append(
                {
                    "record_id": record_id,
                    "detail_type": detail_type,
                }
            )

            # Detail table insert (with record_id included)
            creation_data["record_id"] = record_id
            detail_values_list.append(creation_data)

        if not base_values_list:
            return []

        # Insert into base table first
        base_stmt = (
            insert(EventRecordDetail).values(base_values_list).on_conflict_do_nothing(index_elements=["record_id"])
        )
        db_session.execute(base_stmt)

        # Then insert into the specific detail table
        model = WorkoutDetails if detail_type == "workout" else SleepDetails
        detail_stmt = insert(model).values(detail_values_list).on_conflict_do_nothing(index_elements=["record_id"])
        db_session.execute(detail_stmt)
        db_session.commit()

        # Return empty list (ON CONFLICT DO NOTHING means we can't track which were inserted)
        return []

    def get_by_record_id(self, db_session: DbSession, record_id: UUID) -> EventRecordDetail | None:
        """Get detail by its associated event record ID."""
        return db_session.query(EventRecordDetail).filter(EventRecordDetail.record_id == record_id).one_or_none()
