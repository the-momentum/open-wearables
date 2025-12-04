from datetime import datetime, timedelta, timezone

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

    def get_total_count_week_ago(self, db_session: DbSession) -> int:
        """Get total count of users from 7 days ago."""
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        return db_session.query(func.count(self.model.id)).filter(self.model.created_at <= week_ago).scalar() or 0
