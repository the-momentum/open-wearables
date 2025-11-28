from logging import Logger, getLogger

from app.database import DbSession
from app.models import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate, UserCreateInternal, UserUpdate
from app.services.services import AppService


class UserService(AppService[UserRepository, User, UserCreate, UserUpdate]):
    def __init__(self, log: Logger, **kwargs):
        super().__init__(
            crud_model=UserRepository,
            model=User,
            log=log,
            **kwargs,
        )

    def create(self, db_session: DbSession, creator: UserCreate) -> User:
        """Create a user with server-generated id and created_at."""
        creation_data = creator.model_dump()
        # Server generates id and created_at
        internal_creator = UserCreateInternal(**creation_data)

        return super().create(db_session, internal_creator)


user_service = UserService(log=getLogger(__name__))
