from app.database import DbSession
from app.models import User
from app.repositories import CrudRepository
from app.schemas import UserCreate, UserUpdate


class UserRepository(CrudRepository[User, UserCreate, UserUpdate]):
    def __init__(self, model: type[User]):
        super().__init__(model)

    def get_user_by_auth0_id(self, db_session: DbSession, auth0_id: str) -> User | None:
        return db_session.query(self.model).filter(self.model.auth0_id == auth0_id).one_or_none()

