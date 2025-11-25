from datetime import datetime, timezone
from logging import Logger, getLogger
from uuid import uuid4

from app.database import DbSession
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

    def create(self, db_session: DbSession, creator: UserCreate) -> User:
        """Create a user with server-generated id and created_at."""
        creation_data = creator.model_dump()
        # Server generates id and created_at
        creation_data["id"] = uuid4()
        creation_data["created_at"] = datetime.now(timezone.utc)
        
        creation = self.crud.model(**creation_data)
        db_session.add(creation)
        db_session.commit()
        db_session.refresh(creation)
        
        self.logger.debug(f"Created {self.name} with ID: {creation.id}.")
        return creation


user_service = UserService(log=getLogger(__name__))
