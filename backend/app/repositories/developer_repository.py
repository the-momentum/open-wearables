from app.models import Developer
from app.repositories.repositories import CrudRepository
from app.schemas.model_crud.user_management import DeveloperCreateInternal, DeveloperUpdateInternal


class DeveloperRepository(CrudRepository[Developer, DeveloperCreateInternal, DeveloperUpdateInternal]):
    def __init__(self, model: type[Developer]):
        super().__init__(model)
