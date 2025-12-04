from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from app.database import DbSession
from app.models import User, UserConnection
from app.schemas.oauth import ConnectionStatus


class SystemInfoRepository:
    """Repository for system dashboard information queries."""

    def get_total_users_count(self, db_session: DbSession) -> int:
        """Get total count of users."""
        return db_session.query(func.count(User.id)).scalar() or 0

    def get_total_users_count_week_ago(self, db_session: DbSession) -> int:
        """Get total count of users from 7 days ago."""
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        return (
            db_session.query(func.count(User.id))
            .filter(User.created_at <= week_ago)
            .scalar()
            or 0
        )

    def get_active_connections_count(self, db_session: DbSession) -> int:
        """Get count of active connections."""
        return (
            db_session.query(func.count(UserConnection.id))
            .filter(UserConnection.status == ConnectionStatus.ACTIVE)
            .scalar()
            or 0
        )

    def get_active_connections_count_week_ago(self, db_session: DbSession) -> int:
        """Get count of active connections from 7 days ago."""
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        return (
            db_session.query(func.count(UserConnection.id))
            .filter(
                UserConnection.status == ConnectionStatus.ACTIVE,
                UserConnection.created_at <= week_ago,
            )
            .scalar()
            or 0
        )

