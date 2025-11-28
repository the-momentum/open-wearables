from logging import Logger, getLogger
from uuid import UUID

from app.database import DbSession
from app.models import Developer
from app.repositories.developer_repository import DeveloperRepository
from app.schemas.developer import DeveloperCreate, DeveloperCreateInternal, DeveloperUpdate, DeveloperUpdateInternal
from app.services.services import AppService
from app.utils.security import get_password_hash


class DeveloperService(AppService[DeveloperRepository, Developer, DeveloperCreateInternal, DeveloperUpdateInternal]):
    def __init__(self, log: Logger, **kwargs):
        super().__init__(
            crud_model=DeveloperRepository,
            model=Developer,
            log=log,
            **kwargs,
        )

    def create(self, db_session: DbSession, creator: DeveloperCreate) -> Developer:
        """Create a developer with hashed password and server-generated fields."""
        creation_data = creator.model_dump(exclude={"password"})
        hashed_password = get_password_hash(creator.password)

        internal_creator = DeveloperCreateInternal(
            **creation_data,
            hashed_password=hashed_password,
        )
        return super().create(db_session, internal_creator)

    def update(
        self,
        db_session: DbSession,
        object_id: UUID | int,
        updater: DeveloperUpdate,
        raise_404: bool = False,
    ) -> Developer | None:
        """Update a developer, hashing password if provided and setting updated_at."""
        developer = self.get(db_session, object_id, raise_404=raise_404)
        if not developer:
            return None

        update_data = updater.model_dump(exclude={"password"}, exclude_unset=True)
        internal_updater = DeveloperUpdateInternal(**update_data)

        if updater.password:
            internal_updater.hashed_password = get_password_hash(updater.password)

        return self.crud.update(db_session, developer, internal_updater)


developer_service = DeveloperService(log=getLogger(__name__))
