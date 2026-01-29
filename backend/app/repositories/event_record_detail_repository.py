from logging import getLogger
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
logger = getLogger(__name__)


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

        # Build values for child table (workout_details or sleep_details)
        child_values = []
        for creator in creators:
            data = creator.model_dump(exclude_none=True)
            # Remove fields not in child table
            data.pop("detail_type", None)
            # Remove sleep-specific fields when inserting workout details
            if detail_type == "workout":
                for sleep_field in [
                    "sleep_total_duration_minutes",
                    "sleep_time_in_bed_minutes",
                    "sleep_efficiency_score",
                    "sleep_deep_minutes",
                    "sleep_rem_minutes",
                    "sleep_light_minutes",
                    "sleep_awake_minutes",
                    "is_nap",
                ]:
                    data.pop(sleep_field, None)
            # Remove workout-specific fields when inserting sleep details
            elif detail_type == "sleep":
                for workout_field in [
                    "heart_rate_min",
                    "heart_rate_max",
                    "heart_rate_avg",
                    "steps_count",
                    "energy_burned",
                    "distance",
                    "max_speed",
                    "max_watts",
                    "moving_time_seconds",
                    "total_elevation_gain",
                    "average_speed",
                    "average_watts",
                    "elev_high",
                    "elev_low",
                ]:
                    data.pop(workout_field, None)
            child_values.append(data)

        if child_values:
            logger.debug(f"Inserting {len(child_values)} {detail_type} details, sample: {child_values[0]}")

        # Use appropriate model based on detail_type
        model = WorkoutDetails if detail_type == "workout" else SleepDetails

        child_stmt = insert(model).values(child_values).on_conflict_do_nothing(index_elements=["record_id"])
        db_session.execute(child_stmt)
        # NOTE: Caller should commit - allows batching multiple operations

    def get_by_record_id(self, db_session: DbSession, record_id: UUID) -> EventRecordDetail | None:
        """Get detail by its associated event record ID."""
        return db_session.query(EventRecordDetail).filter(EventRecordDetail.record_id == record_id).one_or_none()
