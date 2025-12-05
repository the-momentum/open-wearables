from datetime import datetime
from logging import Logger, getLogger

from app.database import DbSession
from app.models import UserConnection
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas import UserConnectionCreate, UserConnectionUpdate
from app.services.services import AppService


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


user_connection_service = UserConnectionService(log=getLogger(__name__))
