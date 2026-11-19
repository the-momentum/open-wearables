from typing import Any, cast
from uuid import UUID

from psycopg.errors import UniqueViolation
from sqlalchemy import Table, func, null, or_, update
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.exc import IntegrityError

from app.constants.series_types.workout_detail_stats import WORKOUT_DETAIL_STATS
from app.database import DbSession
from app.models import (
    DETAIL_MODELS,
    DetailType,
    EventRecordAggregate,
    EventRecordDetail,
    WorkoutDetails,
)
from app.repositories.aggregate_repository import AggregateRepository
from app.repositories.repositories import CrudRepository
from app.schemas.enums import ComputedBy, EventCategory, SeriesType, get_series_type_id
from app.schemas.model_crud.activities import (
    EventRecordDetailCreate,
    EventRecordDetailUpdate,
    StatColumn,
)


class EventRecordDetailRepository(
    CrudRepository[EventRecordDetail, EventRecordDetailCreate, EventRecordDetailUpdate],
):
    def __init__(self, model: type[EventRecordDetail]):
        super().__init__(model)
        self.event_aggregate_repo = AggregateRepository(EventRecordAggregate)

    def _mirror_workout_stats(
        self, db_session: DbSession, creators: list[EventRecordDetailCreate], detail_type: DetailType
    ) -> None:
        """Mirror a workout's statistic columns into event_record_aggregate, one row per series."""
        if detail_type != EventCategory.WORKOUT:
            return
        rows = [
            {
                "record_id": creator.record_id,
                "series_type_definition_id": get_series_type_id(series_type),
                "computed_by": ComputedBy.PROVIDER,
                stat: value,
                "count": 1,
            }
            for creator in creators
            for field, (series_type, stat) in self._workout_stats(creator).items()
            if (value := getattr(creator, field, None)) is not None
        ]
        if rows:
            self.event_aggregate_repo.upsert(db_session, rows)

    @staticmethod
    def _workout_stats(creator: EventRecordDetailCreate) -> dict[str, tuple[SeriesType, StatColumn]]:
        if creator.energy_series is None:
            return WORKOUT_DETAIL_STATS
        return {**WORKOUT_DETAIL_STATS, "energy_burned": (creator.energy_series, "sum")}

    def _build_detail(self, creator: EventRecordDetailCreate, detail_type: DetailType) -> EventRecordDetail:
        """Construct the concrete detail ORM object without touching the session."""
        model = DETAIL_MODELS.get(detail_type)
        if model is None:
            raise ValueError(f"Unknown detail type: {detail_type}")
        creation_data = creator.model_dump(exclude_none=True)
        if detail_type == EventCategory.SLEEP and creator.sleep_stages:
            # sleep_stages contains datetime fields that JSONB cannot serialize directly;
            # use Pydantic's JSON mode to convert datetimes to ISO strings.
            creation_data["sleep_stages"] = [s.model_dump(mode="json") for s in creator.sleep_stages]
        return model(**creation_data)

    def create(
        self,
        db_session: DbSession,
        creator: EventRecordDetailCreate,
        detail_type: DetailType = EventCategory.WORKOUT,
    ) -> EventRecordDetail:
        """Create a detail record using the appropriate polymorphic model, or refresh the stored one."""
        # exclude_none keeps column defaults on insert; on conflict, a missing value keeps the stored one
        self._upsert(db_session, [self._row(creator, detail_type, exclude_none=True)], detail_type)
        self._mirror_workout_stats(db_session, [creator], detail_type)
        db_session.commit()
        model = DETAIL_MODELS[detail_type]
        return db_session.query(model).filter(model.record_id == creator.record_id).one()

    def create_and_flush(
        self,
        db_session: DbSession,
        creator: EventRecordDetailCreate,
        detail_type: DetailType = EventCategory.WORKOUT,
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
            self._mirror_workout_stats(db_session, [creator], detail_type)
            nested.commit()
            return detail
        except IntegrityError as exc:
            nested.rollback()
            if isinstance(exc.orig, UniqueViolation) and (
                existing := self.get_by_record_id(db_session, creator.record_id, detail_type)
            ):
                return existing
            raise

    def bulk_create(
        self,
        db_session: DbSession,
        creators: list[EventRecordDetailCreate],
        detail_type: DetailType = EventCategory.WORKOUT,
    ) -> None:
        """Bulk create detail records using batch insert."""
        if not creators:
            return
        self._upsert(db_session, [self._row(creator, detail_type) for creator in creators], detail_type)
        self._mirror_workout_stats(db_session, creators, detail_type)
        # NOTE: Caller should commit - allows batching multiple operations

    @staticmethod
    def _table(detail_type: DetailType) -> Table:
        model = DETAIL_MODELS.get(detail_type)
        if model is None:
            raise ValueError(f"Unknown detail type: {detail_type}")
        return cast(Table, model.__table__)

    def _row(self, creator: EventRecordDetailCreate, detail_type: DetailType, exclude_none: bool = False) -> dict:
        columns = self._table(detail_type).columns
        data = creator.model_dump(exclude_none=exclude_none)
        if detail_type == EventCategory.SLEEP and data.get("sleep_stages"):
            data["sleep_stages"] = [s.model_dump(mode="json") for s in creator.sleep_stages]  # ty:ignore[not-iterable]
        # A JSONB None binds as JSON null, which COALESCE would keep over the stored value
        return {
            k: null() if v is None and isinstance(columns[k].type, JSONB) else v
            for k, v in data.items()
            if k in columns
        }

    def _upsert(self, db_session: DbSession, rows: list[dict], detail_type: DetailType) -> None:
        child_table = self._table(detail_type)
        child_stmt = insert(child_table).values(rows)
        # record_id is the conflict key; created_at is an immutable audit column and
        # must not be reset to now() when an existing row is re-synced. A value this write does not
        # carry keeps the stored one, as the mirrored aggregate row does: Garmin sends a workout's
        # steps from one endpoint and its speed from another.
        immutable_on_upsert = {"record_id", "created_at"}
        update_dict = {
            col_name: func.coalesce(child_stmt.excluded[col_name], child_table.c[col_name])
            for col_name in rows[0]
            if col_name not in immutable_on_upsert
        }
        if update_dict:
            # Skips the write when nothing changed, so a plain re-sync costs no new row version
            child_stmt = child_stmt.on_conflict_do_update(
                index_elements=["record_id"],
                set_=update_dict,
                where=or_(*(child_table.c[col].is_distinct_from(value) for col, value in update_dict.items())),
            )
        else:
            child_stmt = child_stmt.on_conflict_do_nothing(index_elements=["record_id"])
        db_session.execute(child_stmt)

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
