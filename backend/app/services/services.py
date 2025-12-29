from logging import Logger
from uuid import UUID

from fastapi import Request
from pydantic import BaseModel

from app.database import BaseDbModel, DbSession
from app.repositories.repositories import CrudRepository
from app.schemas import FilterParams
from app.utils.exceptions import ResourceNotFoundError, handle_exceptions

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
        log: Logger,
        **kwargs,
    ):
        self.crud = crud_model(model)
        self.name = self.crud.model.__name__.lower()
        self.logger = log
        super().__init__(**kwargs)

    def create(self, db_session: DbSession, creator: CreateSchemaType) -> ModelType:
        creation = self.crud.create(db_session, creator)
        self.logger.debug(f"Created {self.name} with ID: {creation.id}.")  # type: ignore[union-attr]
        return creation  # type: ignore[return-value]

    @handle_exceptions
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

        if not (fetched := self.crud.get(db_session, id_to_fetch)) and raise_404:  # type: ignore[arg-type]
            raise ResourceNotFoundError(self.name, id_to_fetch)  # type: ignore[arg-type]

        if fetched and print_log:
            self.logger.debug(f"Fetched {self.name} with ID: {fetched.id}.")
        elif not fetched:
            self.logger.debug(f"{self.name} with ID: {object_id} not found.")

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

        self.logger.debug(f"Fetched {len(fetched)} {self.name}s. Filters: {filter_params.filters}.")

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
            self.logger.debug(f"Updated {self.name} with ID: {fetched.id}.")
            return fetched  # type: ignore[return-value]

    def delete(self, db_session: DbSession, object_id: UUID | str | int, raise_404: bool = False) -> ModelType | None:
        if originator := self.get(db_session, object_id, print_log=False, raise_404=raise_404):
            deleted = self.crud.delete(db_session, originator)
            self.logger.debug(f"Deleted {self.name} with ID: {deleted.id}.")
            return deleted  # type: ignore[return-value]
