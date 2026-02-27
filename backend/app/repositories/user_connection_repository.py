from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import and_, func

from app.database import DbSession
from app.models import UserConnection
from app.repositories.repositories import CrudRepository
from app.schemas import ConnectionStatus, UserConnectionCreate, UserConnectionUpdate


class UserConnectionRepository(CrudRepository[UserConnection, UserConnectionCreate, UserConnectionUpdate]):
    """Repository for managing OAuth user connections to fitness providers."""

    def __init__(self, model: type[UserConnection] = UserConnection):
        super().__init__(model)

    def get_active_count(self, db_session: DbSession) -> int:
        """Get total count of active connections."""
        return (
            db_session.query(func.count(self.model.id)).filter(self.model.status == ConnectionStatus.ACTIVE).scalar()
            or 0
        )

    def get_active_count_in_range(self, db_session: DbSession, start_date: datetime, end_date: datetime) -> int:
        """Get count of active connections created within a date range."""
        return (
            db_session.query(func.count(self.model.id))
            .filter(
                and_(
                    self.model.status == ConnectionStatus.ACTIVE,
                    self.model.created_at >= start_date,
                    self.model.created_at < end_date,
                ),
            )
            .scalar()
            or 0
        )

    def get_by_user_and_provider(
        self,
        db_session: DbSession,
        user_id: UUID,
        provider: str,
    ) -> UserConnection | None:
        """Get connection for specific user and provider."""
        return (
            db_session.query(self.model)
            .filter(
                and_(
                    self.model.user_id == user_id,
                    self.model.provider == provider,
                ),
            )
            .one_or_none()
        )

    def get_active_connection(
        self,
        db_session: DbSession,
        user_id: UUID,
        provider: str,
    ) -> UserConnection | None:
        """Get active connection for specific user and provider."""
        return (
            db_session.query(self.model)
            .filter(
                and_(
                    self.model.user_id == user_id,
                    self.model.provider == provider,
                    self.model.status == ConnectionStatus.ACTIVE,
                ),
            )
            .one_or_none()
        )

    def get_by_provider_user_id(
        self,
        db_session: DbSession,
        provider: str,
        provider_user_id: str,
    ) -> UserConnection | None:
        """Get connection by provider and provider's user ID.

        Useful for webhook processing where we receive provider's user ID
        and need to find our internal user.
        """
        return (
            db_session.query(self.model)
            .filter(
                and_(
                    self.model.provider == provider,
                    self.model.provider_user_id == provider_user_id,
                    self.model.status == ConnectionStatus.ACTIVE,
                ),
            )
            .one_or_none()
        )

    def get_by_user_id(
        self,
        db_session: DbSession,
        user_id: UUID,
    ) -> list[UserConnection]:
        """Get all connections for a specific user."""
        return (
            db_session.query(self.model)
            .filter(self.model.user_id == user_id)
            .order_by(self.model.created_at.desc())
            .all()
        )

    def get_expiring_tokens(self, db_session: DbSession, minutes_threshold: int = 5) -> list[UserConnection]:
        """Get connections with tokens expiring soon (for background refresh)."""
        now = datetime.now(timezone.utc)

        threshold_time = now + timedelta(minutes=minutes_threshold)

        return (
            db_session.query(self.model)
            .filter(
                and_(
                    self.model.status == ConnectionStatus.ACTIVE,
                    self.model.token_expires_at <= threshold_time,
                ),
            )
            .all()
        )

    def mark_as_revoked(self, db_session: DbSession, connection: UserConnection) -> UserConnection:
        """Mark connection as revoked (when refresh token fails)."""
        connection.status = ConnectionStatus.REVOKED
        connection.updated_at = datetime.now(timezone.utc)
        db_session.add(connection)
        db_session.commit()
        db_session.refresh(connection)
        return connection

    def update_scope(self, db_session: DbSession, connection: UserConnection, scope: str | None) -> UserConnection:
        """Update connection scope (e.g. when user changes permissions on Garmin Connect)."""
        connection.scope = scope
        connection.updated_at = datetime.now(timezone.utc)
        db_session.add(connection)
        db_session.commit()
        db_session.refresh(connection)
        return connection

    def update_tokens(
        self,
        db_session: DbSession,
        connection: UserConnection,
        access_token: str,
        refresh_token: str | None,
        expires_in: int,
    ) -> UserConnection:
        """Update connection with new tokens after refresh."""

        connection.access_token = access_token
        if refresh_token:
            connection.refresh_token = refresh_token
        connection.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        connection.updated_at = datetime.now(timezone.utc)
        db_session.add(connection)
        db_session.commit()
        db_session.refresh(connection)
        return connection

    def update_connection_info(
        self,
        db_session: DbSession,
        connection: UserConnection,
        access_token: str,
        refresh_token: str | None,
        expires_in: int,
        provider_user_id: str | None = None,
        provider_username: str | None = None,
        scope: str | None = None,
    ) -> UserConnection:
        """Update connection with new tokens and user info."""
        connection.access_token = access_token
        if refresh_token:
            connection.refresh_token = refresh_token
        connection.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        if provider_user_id and not connection.provider_user_id:
            connection.provider_user_id = provider_user_id
        if provider_username and not connection.provider_username:
            connection.provider_username = provider_username
        if scope and connection.scope != scope:
            connection.scope = scope

        connection.updated_at = datetime.now(timezone.utc)
        db_session.add(connection)
        db_session.commit()
        db_session.refresh(connection)
        return connection

    def update_last_synced_at(self, db_session: DbSession, connection: UserConnection) -> UserConnection:
        """Update the last synced timestamp."""
        connection.last_synced_at = datetime.now(timezone.utc)
        db_session.add(connection)
        db_session.commit()
        db_session.refresh(connection)
        return connection

    def get_all_active_by_user(self, db_session: DbSession, user_id: UUID) -> list[UserConnection]:
        """Get all active connections for a specific user."""
        return (
            db_session.query(self.model)
            .filter(
                and_(
                    self.model.user_id == user_id,
                    self.model.status == ConnectionStatus.ACTIVE,
                ),
            )
            .all()
        )

    def get_all_active_users(self, db_session: DbSession) -> list[UUID]:
        """Get all unique user IDs that have active connections."""
        return [
            row.user_id
            for row in db_session.query(self.model.user_id)
            .filter(self.model.status == ConnectionStatus.ACTIVE)
            .distinct()
            .all()
        ]

    def ensure_sdk_connection(
        self,
        db_session: DbSession,
        user_id: UUID,
        provider: str,
    ) -> UserConnection:
        """Ensure an SDK-based connection exists for a user and provider.

        SDK-based providers (like Apple Health) don't use OAuth tokens.
        This method creates or returns an existing connection without tokens.
        """
        existing = self.get_by_user_and_provider(db_session, user_id, provider)
        if existing:
            # Reactivate if revoked
            if existing.status != ConnectionStatus.ACTIVE:
                existing.status = ConnectionStatus.ACTIVE
                existing.updated_at = datetime.now(timezone.utc)
                db_session.add(existing)
                db_session.commit()
                db_session.refresh(existing)
            return existing

        # Create new SDK connection (no tokens needed)
        connection = UserConnection(
            id=uuid4(),
            user_id=user_id,
            provider=provider,
            access_token=None,
            refresh_token=None,
            token_expires_at=None,
            status=ConnectionStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(connection)
        db_session.commit()
        db_session.refresh(connection)
        return connection
