from logging import Logger, getLogger
from uuid import UUID

from app.database import DbSession
from app.models import User
from app.repositories.user_repository import UserRepository
from app.schemas import UserCreate, UserCreateInternal, UserUpdate, UserUpdateInternal
from app.services.services import AppService


class UserService(AppService[UserRepository, User, UserCreateInternal, UserUpdateInternal]):
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


user_service = UserService(log=getLogger(__name__))
