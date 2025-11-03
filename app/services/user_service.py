from logging import Logger, getLogger

from app.database import DbSession
from app.models import User
from app.repositories import UserRepository
from app.schemas import UserCreate, UserUpdate
from app.services import AppService
from app.utils.exceptions import handle_exceptions


class UserService(AppService[UserRepository, User, UserCreate, UserUpdate]):
    def __init__(self, log: Logger, **kwargs):
        super().__init__(
            crud_model=UserRepository,
            model=User,
            log=log,
            **kwargs
        )
        self.user_repository = UserRepository(User)

    def get_or_create_user(self, db_session: DbSession, auth0_id: str, email: str) -> User:
        if not auth0_id or not email:
            raise ValueError("auth0_id and email are required")
        
        user = self._get_user_by_auth0_id(db_session, auth0_id)
        
        if user:
            if str(user.email) != email:
                user_update = UserUpdate(email=email)
                user = self.update(db_session, user.id, user_update)
            return user
        
        user_create = UserCreate(
            auth0_id=auth0_id,
            email=email
        )
        
        return self.create(db_session, user_create)

    def _get_user_by_auth0_id(self, db_session: DbSession, auth0_id: str) -> User | None:
        return self.user_repository.get_user_by_auth0_id(db_session, auth0_id)


user_service = UserService(log=getLogger(__name__))
