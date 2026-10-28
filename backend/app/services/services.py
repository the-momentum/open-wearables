from uuid import UUID

from fastapi import Request
from pydantic import BaseModel

from app.database import BaseDbModel, DbSession
from app.repositories.repositories import CrudRepository
from app.schemas.utils import FilterParams
from app.utils.exceptions import ResourceNotFoundError
from app.utils.structured_logging import get_logger

logger = get_logger(__name__)

type OptRequest = Request | None


class AppService[
    CrudModelType: CrudRepository,
    ModelType: BaseDbModel,
    CreateSchemaType: BaseModel,
    UpdateSchemaType: BaseModel,
]:
    """Class to prepare CrudRepository to being used by API views."""

    def __init__(
        self,
        crud_model: type[CrudModelType],
        model: type[ModelType],
        **kwargs,
    ):
        self.crud = crud_model(model)
        self.name = self.crud.model.__name__.lower()
        super().__init__(**kwargs)

    def create(self, db_session: DbSession, creator: CreateSchemaType) -> ModelType:
        creation = self.crud.create(db_session, creator)
        logger.debug("Created object", model=self.name, object_id=str(creation.id))  # ty:ignore[unresolved-attribute]
        return creation  # ty:ignore[invalid-return-type]

    def get(
        self,
        db_session: DbSession,
        object_id: UUID | str | int,
        raise_404: bool = False,
        print_log: bool = True,
    ) -> ModelType | None:
        # For str IDs, try to convert to UUID if it looks like one, otherwise pass as-is
        if isinstance(object_id, str):
            try:
                id_to_fetch: UUID | int | str = UUID(object_id)
            except ValueError:
                id_to_fetch = object_id
        else:
            id_to_fetch = object_id

        if not (fetched := self.crud.get(db_session, id_to_fetch)) and raise_404:
            raise ResourceNotFoundError(self.name, id_to_fetch)  # ty:ignore[invalid-argument-type]

        if fetched and print_log:
            logger.debug("Fetched object", model=self.name, object_id=str(fetched.id))
        elif not fetched:
            logger.debug("Object not found", model=self.name, object_id=str(object_id))

        return fetched

    def get_all(
        self,
        db_session: DbSession,
        filter_params: FilterParams,
        raise_404: bool = False,
    ) -> list[ModelType]:
        filter_params.validate_against_model(self.crud.model)

        offset = (filter_params.page - 1) * filter_params.limit

        fetched = self.crud.get_all(
            db_session,
            filter_params.filters,
            offset,
            filter_params.limit,
            filter_params.sort_by,
        )

        if not fetched and raise_404:
            raise ResourceNotFoundError(self.name)

        logger.debug(
            "Fetched objects",
            model=self.name,
            count=len(fetched),
            filter_fields=sorted(filter_params.filters),
        )

        return fetched

    def update(
        self,
        db_session: DbSession,
        object_id: UUID | str | int,
        updater: UpdateSchemaType,
        raise_404: bool = False,
    ) -> ModelType | None:
        if originator := self.get(db_session, object_id, print_log=False, raise_404=raise_404):
            fetched = self.crud.update(db_session, originator, updater)
            logger.debug("Updated object", model=self.name, object_id=str(fetched.id))
            return fetched

    def delete(self, db_session: DbSession, object_id: UUID | str | int, raise_404: bool = False) -> ModelType | None:
        if originator := self.get(db_session, object_id, print_log=False, raise_404=raise_404):
            deleted = self.crud.delete(db_session, originator)
            logger.debug("Deleted object", model=self.name, object_id=str(deleted.id))
            return deleted
