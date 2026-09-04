from contextlib import suppress
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, Exists, case, func, literal, null, nullsfirst, nullslast, or_, select, true
from sqlalchemy.dialects.postgresql import aggregate_order_by, array_agg
from sqlalchemy.orm import Query, aliased

from app.database import DbSession
from app.models import User
from app.models.user_connection import UserConnection
from app.repositories.repositories import CrudRepository
from app.schemas.auth import ConnectionStatus
from app.schemas.model_crud.user_management import (
    USER_SORT_COLUMNS,
    UserCreateInternal,
    UserInclude,
    UserQueryParams,
    UserUpdateInternal,
)


def _connection_exists(*conditions: ColumnElement[bool]) -> Exists:
    """Build a correlated EXISTS over the connections of the outer user row."""
    return select(literal(1)).where(UserConnection.user_id == User.id, *conditions).correlate(User).exists()


class UserRepository(CrudRepository[User, UserCreateInternal, UserUpdateInternal]):
    def __init__(self, model: type[User]):
        super().__init__(model)

    def get_by_email(self, db_session: DbSession, email: str | None) -> User | None:
        if email is None:
            return None
        return db_session.query(self.model).filter(self.model.email == email).one_or_none()

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
    ) -> tuple[list[tuple[User, datetime | None, str | None, bool, list[dict[str, Any]] | None]], int]:
        """Get users with filtering, searching, and pagination.

        The page is selected before the lateral join, so connections are looked up once per
        returned row rather than once per user in the table.

        Args:
            db_session: The database session.
            query_params: The query parameters.

        Returns:
            A tuple of (results, total_count) where each result is a
            (User, last_synced_at, last_synced_provider, has_active_connection, connections) tuple.
            `connections` is None unless the caller requested the expansion.
        """
        query: Query = db_session.query(self.model)
        query = self._apply_filters(query, query_params)

        total_count = query.count()

        query = query.order_by(*self._order_columns(self.model, query_params), self.model.id)
        offset = (query_params.page - 1) * query_params.limit
        page = query.offset(offset).limit(query_params.limit).subquery()
        page_user = aliased(self.model, page)

        summary = self._connection_summary(page_user, query_params)
        rows = (
            db_session.query(page_user, *summary.c)
            .outerjoin(summary, true())
            .order_by(*self._order_columns(page_user, query_params, summary.c.last_synced_at), page_user.id)
            .all()
        )

        return rows, total_count

    def _apply_filters(self, query: Query, query_params: UserQueryParams) -> Query:
        """Narrow the user query. Applied before the count so totals match the page."""
        if query_params.search:
            # Escape special LIKE characters
            escaped_search = query_params.search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            search_term = f"%{escaped_search}%"
            matches: list[ColumnElement[bool]] = [
                self.model.email.ilike(search_term, escape="\\"),
                self.model.first_name.ilike(search_term, escape="\\"),
                self.model.last_name.ilike(search_term, escape="\\"),
            ]
            # Admins paste user ids copied from the UI, logs and Sentry into the same search box.
            with suppress(ValueError):
                matches.append(self.model.id == UUID(query_params.search))
            query = query.filter(or_(*matches))

        if query_params.email:
            query = query.filter(self.model.email == query_params.email)

        if query_params.external_user_id:
            query = query.filter(self.model.external_user_id == query_params.external_user_id)

        if query_params.provider or query_params.connection_status:
            conditions: list[ColumnElement[bool]] = []
            if query_params.provider:
                conditions.append(UserConnection.provider.in_([p.value for p in query_params.provider]))
            if query_params.connection_status:
                conditions.append(UserConnection.status == query_params.connection_status)
            query = query.filter(_connection_exists(*conditions))

        if query_params.has_active_connection is not None:
            has_active = _connection_exists(UserConnection.status == ConnectionStatus.ACTIVE)
            query = query.filter(has_active if query_params.has_active_connection else ~has_active)

        if query_params.last_synced_before is not None:
            # Anti-join rather than HAVING over max(last_synced_at): keeps the count cheap and
            # includes users whose connections never synced.
            query = query.filter(~_connection_exists(UserConnection.last_synced_at >= query_params.last_synced_before))

        return query

    def _order_columns(
        self,
        model: Any,
        query_params: UserQueryParams,
        last_synced_at: ColumnElement[Any] | None = None,
    ) -> list[ColumnElement[Any]]:
        """Resolve sort_by to ORDER BY expressions on the given user entity.

        Args:
            model: The user entity to order by.
            query_params: The query parameters.
            last_synced_at: Already-computed sync timestamp, to order the page without recomputing it.
        """
        # Validate sort_by against explicit allowlist (defense in depth)
        sort_by_column = query_params.sort_by or "created_at"
        if sort_by_column not in USER_SORT_COLUMNS:
            raise ValueError("Invalid sort column")

        ascending = query_params.sort_order == "asc"
        if sort_by_column == "last_synced_at":
            column = (
                last_synced_at
                if last_synced_at is not None
                else select(func.max(UserConnection.last_synced_at))
                .where(UserConnection.user_id == model.id)
                .correlate(model)
                .scalar_subquery()
            )
            return [nullsfirst(column.asc()) if ascending else nullslast(column.desc())]

        if sort_by_column == "name":
            return [
                nullslast(column.asc() if ascending else column.desc())
                for column in (model.first_name, model.last_name)
            ]

        column = getattr(model, sort_by_column)
        return [column.asc() if ascending else column.desc()]

    def _connection_summary(self, page_user: Any, query_params: UserQueryParams) -> Any:
        """Lateral aggregate of a single user's connections, evaluated once per page row."""
        connection = aliased(UserConnection)
        last_synced_at = func.max(connection.last_synced_at)
        columns: list[ColumnElement[Any]] = [
            last_synced_at.label("last_synced_at"),
            # NULLS LAST parks never-synced providers at the end of the array; the CASE keeps the
            # column NULL when none of them ever synced.
            case(
                (
                    last_synced_at.isnot(None),
                    array_agg(aggregate_order_by(connection.provider, nullslast(connection.last_synced_at.desc())))[1],
                )
            ).label("last_synced_provider"),
            func.coalesce(func.bool_or(connection.status == ConnectionStatus.ACTIVE), False).label(
                "has_active_connection"
            ),
        ]
        if UserInclude.CONNECTIONS in query_params.include:
            columns.append(
                func.jsonb_agg(
                    aggregate_order_by(
                        func.jsonb_build_object(
                            "provider",
                            connection.provider,
                            "status",
                            connection.status,
                            "last_synced_at",
                            connection.last_synced_at,
                        ),
                        connection.provider.asc(),
                    )
                ).label("connections")
            )
        else:
            columns.append(null().label("connections"))

        return select(*columns).where(connection.user_id == page_user.id).correlate(page_user).lateral("conn_summary")
