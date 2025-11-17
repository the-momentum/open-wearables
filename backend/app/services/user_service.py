from logging import Logger, getLogger

from app.models import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate, UserUpdate
from app.services.services import AppService


class UserService(AppService[UserRepository, User, UserCreate, UserUpdate]):
    def __init__(self, log: Logger, **kwargs):
        super().__init__(
            crud_model=UserRepository,
            model=User,
            log=log,
            **kwargs,
        )


user_service = UserService(log=getLogger(__name__))
