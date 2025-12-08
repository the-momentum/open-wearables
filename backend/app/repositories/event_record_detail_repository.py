from typing import Literal
from uuid import UUID

from app.database import DbSession
from app.models import EventRecordDetail, SleepDetails, WorkoutDetails
from app.repositories.repositories import CrudRepository
from app.schemas.event_record_detail import EventRecordDetailCreate, EventRecordDetailUpdate
from app.utils.exceptions import handle_exceptions

DetailType = Literal["workout", "sleep"]


class EventRecordDetailRepository(
    CrudRepository[EventRecordDetail, EventRecordDetailCreate, EventRecordDetailUpdate],
):
    def __init__(self, model: type[EventRecordDetail]):
        super().__init__(model)

    @handle_exceptions
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

    def get_by_record_id(self, db_session: DbSession, record_id: UUID) -> EventRecordDetail | None:
        """Get detail by its associated event record ID."""
        return db_session.query(EventRecordDetail).filter(EventRecordDetail.record_id == record_id).one_or_none()
