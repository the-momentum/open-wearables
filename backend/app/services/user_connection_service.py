from datetime import datetime
from logging import Logger, getLogger
from uuid import UUID

from app.database import DbSession
from app.models import UserConnection
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas import UserConnectionCreate, UserConnectionRead, UserConnectionUpdate
from app.services.services import AppService
from app.utils.exceptions import ResourceNotFoundError, handle_exceptions


class UserConnectionService(
    AppService[UserConnectionRepository, UserConnection, UserConnectionCreate, UserConnectionUpdate],
):
    def __init__(self, log: Logger, **kwargs):
        super().__init__(
            crud_model=UserConnectionRepository,
            model=UserConnection,
            log=log,
            **kwargs,
        )

    def get_active_count_in_range(self, db_session: DbSession, start_date: datetime, end_date: datetime) -> int:
        """Get count of active connections created within a date range."""
        return self.crud.get_active_count_in_range(db_session, start_date, end_date)

    @handle_exceptions
    def get_connections_by_user(self, db_session: DbSession, user_id: UUID) -> list[UserConnectionRead]:
        """Get all connections for a user."""
        connections = self.crud.get_by_user_id(db_session, user_id)
        return [UserConnectionRead.model_validate(conn) for conn in connections]

    @handle_exceptions
    def disconnect(self, db_session: DbSession, user_id: UUID, provider: str) -> None:
        """Disconnect a user from a provider. Raises 404 if connection not found."""
        updated = self.crud.disconnect(db_session, user_id, provider)
        if updated:
            self.logger.info("Disconnected user %s from provider %s", user_id, provider)
            return

        # Nothing updated - check if connection exists (already revoked) or not found
        connection = self.crud.get_by_user_and_provider(db_session, user_id, provider)
        if not connection:
            raise ResourceNotFoundError("connection", user_id)


user_connection_service = UserConnectionService(log=getLogger(__name__))
