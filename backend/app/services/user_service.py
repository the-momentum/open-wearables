from datetime import datetime
from logging import Logger, getLogger
from uuid import UUID

from pydantic import ValidationError

from app.database import DbSession
from app.models import User
from app.repositories.user_repository import UserRepository
from app.schemas.model_crud.user_management import (
    UserCreate,
    UserCreateInternal,
    UserQueryParams,
    UserRead,
    UserUpdate,
    UserUpdateInternal,
)
from app.schemas.utils import OldPaginatedResponse
from app.services.providers.factory import ProviderFactory
from app.services.providers.garmin.backfill_state import force_release_backfill_lock
from app.services.services import AppService
from app.services.sync_coordination import release_stale_primary
from app.services.user_connection_service import user_connection_service
from app.utils.exceptions import ResourceAlreadyExistsError, handle_exceptions
from app.utils.structured_logging import log_structured


class UserService(AppService[UserRepository, User, UserCreateInternal, UserUpdateInternal]):
    def __init__(self, log: Logger, **kwargs):
        super().__init__(
            crud_model=UserRepository,
            model=User,
            log=log,
            **kwargs,
        )

    def get_count_in_range(self, db_session: DbSession, start_date: datetime, end_date: datetime) -> int:
        """Get count of users created within a date range."""
        return self.crud.get_count_in_range(db_session, start_date, end_date)

    @handle_exceptions
    def create(self, db_session: DbSession, creator: UserCreate) -> User:
        """Create a user with server-generated id and created_at."""
        if self.crud.get_by_email(db_session, creator.email):
            raise ResourceAlreadyExistsError("User with this email already exists.")
        creation_data = creator.model_dump()
        internal_creator = UserCreateInternal(**creation_data)
        return super().create(db_session, internal_creator)

    def update(
        self,
        db_session: DbSession,
        object_id: UUID | str | int,
        updater: UserUpdate,
        raise_404: bool = False,
    ) -> User | None:
        """Update a user, setting updated_at automatically."""
        user = self.get(db_session, object_id, raise_404=raise_404)
        if not user:
            return None

        update_data = updater.model_dump(exclude_unset=True)
        internal_updater = UserUpdateInternal(**update_data)
        return self.crud.update(db_session, user, internal_updater)

    def delete(self, db_session: DbSession, object_id: UUID | str | int, raise_404: bool = False) -> User | None:
        """Delete a user by ID."""
        user = self.get(db_session, object_id, raise_404=raise_404)
        if not user:
            return None
        provider_factory = ProviderFactory()
        connections = list(user_connection_service.get_connections_by_user(db_session, user.id))
        for connection in connections:
            if not connection.access_token:
                continue
            try:
                strategy = provider_factory.get_provider(connection.provider)
                if oauth := strategy.oauth:
                    oauth.deregister_user(connection.access_token)
            except Exception as e:
                log_structured(
                    self.logger,
                    "warning",
                    "Failed to deregister user",
                    user_id=user.id,
                    provider=connection.provider,
                    error=str(e),
                )

        # Release any Redis locks held by this user before DB deletion.
        # Must happen before DB delete so we still have provider_user_id from connections.
        try:
            for connection in connections:
                if connection.provider_user_id:
                    for scope in ("pull", "backfill"):
                        release_stale_primary(connection.provider, connection.provider_user_id, scope=scope)
            force_release_backfill_lock(user.id)
        except Exception as e:
            log_structured(
                self.logger,
                "warning",
                "Failed to release Redis locks on user deletion",
                user_id=user.id,
                error=str(e),
            )

        return self.crud.delete(db_session, user)

    @handle_exceptions
    def get_users_paginated(
        self,
        db_session: DbSession,
        query_params: UserQueryParams,
    ) -> OldPaginatedResponse[UserRead]:
        rows, total_count = self.crud.get_users_with_filters(db_session, query_params)

        items = []
        for user, last_synced_at, last_synced_provider, has_active_connection in rows:
            try:
                user_read = UserRead.model_validate(user)
            except ValidationError as exc:
                if not all("email" in e["loc"] for e in exc.errors()):
                    raise
                self.logger.warning("Skipping user %s — invalid email: %s", user.id, user.email)
                total_count -= 1
                continue

            user_read.last_synced_at = last_synced_at
            user_read.last_synced_provider = last_synced_provider
            user_read.has_active_connection = bool(has_active_connection)
            items.append(user_read)

        return OldPaginatedResponse[UserRead](
            items=items,
            total=total_count,
            page=query_params.page,
            limit=query_params.limit,
        )


user_service = UserService(log=getLogger(__name__))
