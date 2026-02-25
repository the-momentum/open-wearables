from datetime import datetime
from logging import Logger, getLogger
from uuid import UUID

from app.database import DbSession
from app.models import User
from app.repositories.user_repository import UserRepository
from app.schemas import UserCreate, UserCreateInternal, UserUpdate, UserUpdateInternal
from app.schemas.common import PaginatedResponse
from app.schemas.user import UserQueryParams, UserRead
from app.services.services import AppService
from app.utils.exceptions import handle_exceptions


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

    def create(self, db_session: DbSession, creator: UserCreate) -> User:
        """Create a user with server-generated id and created_at."""
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

    @handle_exceptions
    def get_users_paginated(
        self,
        db_session: DbSession,
        query_params: UserQueryParams,
    ) -> PaginatedResponse[UserRead]:
        """Get users with filtering, searching, and pagination.

        Args:
            db_session: The database session.
            query_params: The query parameters.

        Returns:
            A paginated response containing the users and the total count of users.
        """
        self.logger.debug(f"Fetching users with pagination: page={query_params.page}, limit={query_params.limit}")

        rows, total_count = self.crud.get_users_with_filters(db_session, query_params)

        self.logger.debug(f"Retrieved {len(rows)} users out of {total_count} total")

        items = []
        for user, last_synced_at in rows:
            user_read = UserRead.model_validate(user)
            user_read.last_synced_at = last_synced_at
            items.append(user_read)

        return PaginatedResponse[UserRead](
            items=items,
            total=total_count,
            page=query_params.page,
            limit=query_params.limit,
        )


user_service = UserService(log=getLogger(__name__))
