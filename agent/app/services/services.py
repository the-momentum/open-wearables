from logging import Logger
from uuid import UUID

from pydantic import BaseModel

from app.database import BaseDbModel, DbSession
from app.repositories import CrudRepository
from app.schemas import FilterParams
from app.utils.exceptions import ResourceNotFoundError, handle_exceptions


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
        log: Logger,
        **kwargs,
    ):
        self.crud = crud_model(model)
        self.name = self.crud.model.__name__.lower()
        self.logger = log
        super().__init__(**kwargs)

    @handle_exceptions
    def create(self, db_session: DbSession, creator: CreateSchemaType) -> ModelType:
        creation = self.crud.create(db_session, creator)
        self.logger.info(f"Created {self.name} with ID: {creation.id}.")
        return creation

    @handle_exceptions
    def get(
        self,
        db_session: DbSession,
        object_id: UUID | int,
        raise_404: bool = False,
        print_log: bool = True,
    ) -> ModelType | None:
        if not (fetched := self.crud.get(db_session, object_id)) and raise_404:
            raise ResourceNotFoundError(self.name, object_id)

        if fetched and print_log:
            self.logger.info(f"Fetched {self.name} with ID: {fetched.id}.")
        elif not fetched:
            self.logger.info(f"{self.name} with ID: {object_id} not found.")

        return fetched

    @handle_exceptions
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

        self.logger.info(f"Fetched {len(fetched)} {self.name}s. Filters: {filter_params.filters}.")

        return fetched

    def update(
        self,
        db_session: DbSession,
        object_id: UUID | int,
        updater: UpdateSchemaType,
        raise_404: bool = False,
    ) -> ModelType | None:
        if originator := self.get(db_session, object_id, print_log=False, raise_404=raise_404):
            fetched = self.crud.update(db_session, originator, updater)
            self.logger.info(f"Updated {self.name} with ID: {fetched.id}.")
            return fetched

    def delete(self, db_session: DbSession, object_id: UUID | int, raise_404: bool = False) -> ModelType | None:
        if originator := self.get(db_session, object_id, print_log=False, raise_404=raise_404):
            deleted = self.crud.delete(db_session, originator)
            self.logger.info(f"Deleted {self.name} with ID: {deleted.id}.")
            return deleted
