from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import ColumnElement, Date, case, cast, exists, func, literal, select
from sqlalchemy.orm import InstrumentedAttribute, Query

from app.database import BaseDbModel, DbSession
from app.models import DataSource
from app.models.series_type_definition import SeriesTypeDefinition
from app.schemas.enums import DeviceType, ProviderName, TimelineBucket, TimelineGroupBy
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


# Rank of a provider or device type missing from the priority tables
UNRANKED_PRIORITY = 99


@dataclass(frozen=True)
class SourceRanking:
    """The configured provider and device type priorities, ordering data sources best first, in Python (``rank``)
    or in SQL (``order_terms``) alike. Sources sharing provider and device type tie; each read breaks the tie."""

    provider_order: Mapping[ProviderName, int]
    device_type_order: Mapping[DeviceType, int]

    @classmethod
    def load(cls, db_session: DbSession) -> "SourceRanking":
        """The priorities as configured now."""
        # Imported here: the provider priority repository builds on this module.
        from app.models import ProviderPriority
        from app.repositories.device_type_priority_repository import DeviceTypePriorityRepository
        from app.repositories.provider_priority_repository import ProviderPriorityRepository

        return cls(
            ProviderPriorityRepository(ProviderPriority).get_priority_order(db_session),
            DeviceTypePriorityRepository().get_priority_order(db_session),
        )

    def rank(self, provider: str | None, device_type: str | None) -> tuple[int, int]:
        """A source's place by its provider and device type, lowest first."""
        return self.provider_order.get(provider, UNRANKED_PRIORITY), self.device_type_order.get(
            device_type, UNRANKED_PRIORITY
        )

    def order_terms(
        self, provider_column: InstrumentedAttribute[str] | ColumnElement[str] = DataSource.provider
    ) -> tuple[ColumnElement, ColumnElement, ColumnElement]:
        """ORDER BY terms ranking sources best first: provider, device type, device model. Assumes ``DataSource``.

        ``provider_column`` is for rows that carry their own provider and may have no source (health scores).
        """
        provider_rank = (
            case(*[(provider_column == p, r) for p, r in self.provider_order.items()], else_=UNRANKED_PRIORITY)
            if self.provider_order
            else literal(UNRANKED_PRIORITY)
        )
        device_rank = (
            case(
                *[(DataSource.device_type == t.value, r) for t, r in self.device_type_order.items()],
                else_=UNRANKED_PRIORITY,
            )
            if self.device_type_order
            else literal(UNRANKED_PRIORITY)
        )
        return provider_rank, device_rank, func.coalesce(DataSource.device_model, "")


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

    def get_by_ids(self, db_session: DbSession, object_ids: Collection[UUID | int | str]) -> Sequence[ModelType]:
        if not object_ids:
            return []
        return db_session.scalars(select(self.model).where(getattr(self.model, "id").in_(object_ids))).all()

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
