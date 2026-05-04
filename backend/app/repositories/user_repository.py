from datetime import datetime

from sqlalchemy import desc, func, nullsfirst, nullslast, or_, select
from sqlalchemy.orm import Query, selectinload

from app.database import DbSession
from app.models import User
from app.models.user_connection import UserConnection
from app.repositories.repositories import CrudRepository
from app.schemas.model_crud.user_management import (
    USER_SORT_COLUMNS,
    UserCreateInternal,
    UserQueryParams,
    UserUpdateInternal,
)


class UserRepository(CrudRepository[User, UserCreateInternal, UserUpdateInternal]):
    def __init__(self, model: type[User]):
        super().__init__(model)

    def get_total_count(self, db_session: DbSession) -> int:
        """Get total count of users."""
        return db_session.query(func.count(self.model.id)).scalar() or 0

    def get_count_in_range(self, db_session: DbSession, start_date: datetime, end_date: datetime) -> int:
        """Get count of users created within a date range."""
        return (
            db_session.query(func.count(self.model.id))
            .filter(self.model.created_at >= start_date, self.model.created_at < end_date)
            .scalar()
            or 0
        )

    def get_users_with_filters(
        self,
        db_session: DbSession,
        query_params: UserQueryParams,
    ) -> tuple[list[tuple[User, datetime | None, str | None]], int]:
        """Get users with filtering, searching, and pagination.

        Args:
            db_session: The database session.
            query_params: The query parameters.

        Returns:
            A tuple containing a list of (user, last_synced_at, last_synced_provider) tuples
            and the total count of users.
        """
        query: Query = db_session.query(self.model).options(selectinload(self.model.personal_record))

        if query_params.search:
            # Escape special LIKE characters
            escaped_search = query_params.search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            search_term = f"%{escaped_search}%"
            query = query.filter(
                or_(
                    self.model.email.ilike(search_term, escape="\\"),
                    self.model.first_name.ilike(search_term, escape="\\"),
                    self.model.last_name.ilike(search_term, escape="\\"),
                ),
            )

        if query_params.email:
            query = query.filter(self.model.email == query_params.email)

        if query_params.external_user_id:
            query = query.filter(self.model.external_user_id == query_params.external_user_id)

        total_count = query.count()

        # Add correlated subqueries for last sync info
        last_synced_subq = (
            select(func.max(UserConnection.last_synced_at))
            .where(UserConnection.user_id == User.id)
            .correlate(User)
            .scalar_subquery()
            .label("last_synced_at")
        )
        last_synced_provider_subq = (
            select(UserConnection.provider)
            .where(UserConnection.user_id == User.id)
            .where(UserConnection.last_synced_at.isnot(None))
            .order_by(UserConnection.last_synced_at.desc())
            .limit(1)
            .correlate(User)
            .scalar_subquery()
            .label("last_synced_provider")
        )
        query = query.add_columns(last_synced_subq, last_synced_provider_subq)

        # Validate sort_by against explicit allowlist (defense in depth)
        sort_by_column = query_params.sort_by or "created_at"
        if sort_by_column not in USER_SORT_COLUMNS:
            raise ValueError("Invalid sort column")

        if sort_by_column == "last_synced_at":
            sort_column = last_synced_subq
            if query_params.sort_order == "asc":
                order_column = nullsfirst(sort_column.asc())
            else:
                order_column = nullslast(sort_column.desc())
        else:
            sort_column = getattr(self.model, sort_by_column)
            order_column = sort_column if query_params.sort_order == "asc" else desc(sort_column)
        query = query.order_by(order_column, self.model.id)

        offset = (query_params.page - 1) * query_params.limit
        query = query.offset(offset).limit(query_params.limit)

        return query.all(), total_count
