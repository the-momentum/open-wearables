from datetime import datetime

from sqlalchemy import func

from app.database import DbSession
from app.models import User
from app.repositories.repositories import CrudRepository
from app.schemas.user import UserCreateInternal, UserUpdateInternal


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
