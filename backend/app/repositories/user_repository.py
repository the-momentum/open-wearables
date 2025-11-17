from app.models import User
from app.repositories.repositories import CrudRepository
from app.schemas import UserCreate, UserUpdate


class UserRepository(CrudRepository[User, UserCreate, UserUpdate]):
    def __init__(self, model: type[User]):
        super().__init__(model)
