from app.models import User
from app.repositories.repositories import CrudRepository
from app.schemas.user import UserCreateInternal, UserUpdateInternal


class UserRepository(CrudRepository[User, UserCreateInternal, UserUpdateInternal]):
    def __init__(self, model: type[User]):
        super().__init__(model)
