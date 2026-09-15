from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import ColumnElement, Date, cast, exists, func
from sqlalchemy.orm import InstrumentedAttribute, Query

from app.database import BaseDbModel, DbSession
from app.models import DataSource
from app.models.series_type_definition import SeriesTypeDefinition
from app.schemas.enums import TimelineBucket, TimelineGroupBy
from app.schemas.model_crud.activities.source_filters import SourceFilterParams
from app.utils.duplicates import handle_duplicates
from app.utils.exceptions import handle_exceptions


def utc_bucket_start(
    bucket: TimelineBucket,
    column: InstrumentedAttribute[datetime] | ColumnElement[datetime],
) -> ColumnElement[date]:
    """Truncate a timestamptz column to the start of its UTC day or week.

    ``timezone('UTC', ts)`` pins the truncation to UTC; a bare date_trunc would follow the
    session timezone and place the same row in a different bucket per connection.
    """
    return cast(func.date_trunc(bucket.value, func.timezone("UTC", column)), Date)


def source_filter_conditions(
    params: SourceFilterParams,
    data_source_id_column: InstrumentedAttribute[UUID],
) -> list[ColumnElement[bool]]:
    """Conditions narrowing a read to one origin. Assumes ``DataSource`` is queried or joined.

    ``data_source_id_column`` is whichever column holds the id on the queried table, so the same
    filters serve a row table (``<model>.data_source_id``) and ``DataSource`` itself (``.id``).
    """
    conditions: list[ColumnElement[bool]] = []
    if params.provider:
        conditions.append(DataSource.provider == params.provider)
    if params.source:
        conditions.append(DataSource.source == params.source)
    if params.device_model:
        conditions.append(DataSource.device_model == params.device_model)
    if params.data_source_id:
        conditions.append(data_source_id_column == params.data_source_id)
    return conditions


def timeline_key_column(group_by: TimelineGroupBy) -> InstrumentedAttribute[str]:
    """Column a data point timeline series is keyed by.

    Explicit so a new grouping fails loudly here rather than silently reading as series type.
    """
    match group_by:
        case TimelineGroupBy.PROVIDER:
            return DataSource.provider
        case TimelineGroupBy.SERIES_TYPE:
            return SeriesTypeDefinition.code
        case _:
            raise ValueError(f"{group_by} does not key a data point timeline")


class CrudRepository[
    ModelType: BaseDbModel,
    CreateSchemaType: BaseModel,
    UpdateSchemaType: BaseModel,
]:
    """Class to manage database operations."""

    def __init__(self, model: type[ModelType]):
        self.model = model

    @handle_exceptions
    @handle_duplicates
    def create(self, db_session: DbSession, creator: CreateSchemaType) -> ModelType:
        creation_data = creator.model_dump()
        creation = self.model(**creation_data)
        db_session.add(creation)
        db_session.commit()
        db_session.refresh(creation)
        return creation

    def exists_any(self, db_session: DbSession) -> bool:
        return db_session.query(exists().where(getattr(self.model, "id").isnot(None))).scalar()

    def get(self, db_session: DbSession, object_id: UUID | int | str) -> ModelType | None:
        return db_session.query(self.model).filter(getattr(self.model, "id") == object_id).one_or_none()

    def get_all(
        self,
        db_session: DbSession,
        filters: dict[str, str],
        offset: int,
        limit: int,
        sort_by: str | None,
    ) -> list[ModelType]:
        query: Query = db_session.query(self.model)

        for field, value in filters.items():
            query = query.filter(getattr(self.model, field) == value)

        if sort_by:
            query = query.order_by(getattr(self.model, sort_by))

        return query.offset(offset).limit(limit).all()

    def update(
        self,
        db_session: DbSession,
        originator: ModelType,
        updater: UpdateSchemaType,
    ) -> ModelType:
        updater_data = updater.model_dump(exclude_none=True)
        for field_name, field_value in updater_data.items():
            setattr(originator, field_name, field_value)
        db_session.add(originator)
        db_session.commit()
        db_session.refresh(originator)
        return originator

    def delete(self, db_session: DbSession, originator: ModelType) -> ModelType:
        db_session.delete(originator)
        db_session.commit()
        return originator

    def delete_flush(self, db_session: DbSession, originator: ModelType) -> None:
        """Delete the object and flush without committing; caller is responsible for the commit."""
        db_session.delete(originator)
        db_session.flush()
