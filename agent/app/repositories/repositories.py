from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Query

from app.database import BaseDbModel, DbSession


class CrudRepository[
    ModelType: BaseDbModel,
    CreateSchemaType: BaseModel,
    UpdateSchemaType: BaseModel,
]:
    """Class to manage database operations."""

    def __init__(self, model: type[ModelType]):
        self.model = model

    def create(self, db_session: DbSession, creator: CreateSchemaType) -> ModelType:
        creation_data = creator.model_dump()
        creation = self.model(**creation_data)
        db_session.add(creation)
        db_session.commit()
        db_session.refresh(creation)
        return creation

    def get(self, db_session: DbSession, object_id: UUID | int) -> ModelType | None:
        return db_session.query(self.model).filter(self.model.id == object_id).one_or_none()  # type: ignore

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


class AsyncCrudRepository[
    ModelType: BaseDbModel,
    CreateSchemaType: BaseModel,
    UpdateSchemaType: BaseModel,
]:
    """Class to manage async database operations."""

    def __init__(self, model: type[ModelType]):
        self.model = model

    async def create(self, db_session: AsyncSession, creator: CreateSchemaType) -> ModelType:
        creation_data = creator.model_dump()
        creation = self.model(**creation_data)
        db_session.add(creation)
        await db_session.commit()
        await db_session.refresh(creation)
        return creation

    async def get(self, db_session: AsyncSession, object_id: UUID | int) -> ModelType | None:
        result = await db_session.execute(select(self.model).where(self.model.id == object_id))  # type: ignore
        return result.scalar_one_or_none()

    async def get_all(
        self,
        db_session: AsyncSession,
        filters: dict[str, str],
        offset: int,
        limit: int,
        sort_by: str | None,
    ) -> list[ModelType]:
        query = select(self.model)

        for field, value in filters.items():
            query = query.where(getattr(self.model, field) == value)

        if sort_by:
            query = query.order_by(getattr(self.model, sort_by))

        result = await db_session.execute(query.offset(offset).limit(limit))
        return list(result.scalars().all())

    async def update(
        self,
        db_session: AsyncSession,
        originator: ModelType,
        updater: UpdateSchemaType,
    ) -> ModelType:
        updater_data = updater.model_dump(exclude_none=True)
        for field_name, field_value in updater_data.items():
            setattr(originator, field_name, field_value)
        db_session.add(originator)
        await db_session.commit()
        await db_session.refresh(originator)
        return originator

    async def delete(self, db_session: AsyncSession, originator: ModelType) -> ModelType:
        await db_session.delete(originator)
        await db_session.commit()
        return originator
