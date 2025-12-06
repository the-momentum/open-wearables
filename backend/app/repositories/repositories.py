from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.orm import Query

from app.database import BaseDbModel, DbSession
from app.utils.exceptions import handle_exceptions


class CrudRepository[
    ModelType: BaseDbModel,
    CreateSchemaType: BaseModel,
    UpdateSchemaType: BaseModel,
]:
    """Class to manage database operations."""

    def __init__(self, model: type[ModelType]):
        self.model = model

    @handle_exceptions
    def create(self, db_session: DbSession, creator: CreateSchemaType) -> ModelType:
        creation_data = creator.model_dump()
        creation = self.model(**creation_data)
        db_session.add(creation)
        db_session.commit()
        db_session.refresh(creation)
        return creation

    def get(self, db_session: DbSession, object_id: UUID | int) -> ModelType | None:
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
