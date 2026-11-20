from uuid import UUID

from app.database import DbSession
from app.models import Developer
from app.repositories.developer_repository import DeveloperRepository
from app.repositories.refresh_token_repository import refresh_token_repository
from app.schemas.model_crud.user_management import (
    DeveloperCreate,
    DeveloperCreateInternal,
    DeveloperUpdate,
    DeveloperUpdateInternal,
)
from app.services.services import AppService
from app.utils.security import get_password_hash
from app.utils.structured_logging import get_logger

logger = get_logger(__name__)


class DeveloperService(AppService[DeveloperRepository, Developer, DeveloperCreateInternal, DeveloperUpdateInternal]):
    def __init__(self, **kwargs):
        super().__init__(
            crud_model=DeveloperRepository,
            model=Developer,
            **kwargs,
        )

    def register(self, db_session: DbSession, creator: DeveloperCreate) -> Developer:
        """Create a developer with hashed password and server-generated fields."""
        creation_data = creator.model_dump(exclude={"password"})
        internal_creator = DeveloperCreateInternal(
            **creation_data,
            hashed_password=get_password_hash(creator.password),
        )
        return super().create(db_session, internal_creator)

    def get_by_email(self, db_session: DbSession, email: str) -> Developer | None:
        return self.crud.get_by_email(db_session, email)

    def list_all(self, db_session: DbSession) -> list[Developer]:
        return self.crud.list_all(db_session)

    def update_developer_info(
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
            # Sessions issued before the password change must not survive it. Revoke before
            # persisting the new hash: if the update fails, the old password still works and
            # the user simply logs in again, which is safer than the reverse order.
            revoked = refresh_token_repository.revoke_all_for_developer(db_session, developer.id)
            logger.info(
                "Revoked refresh tokens after password change",
                developer_id=str(developer.id),
                revoked_count=revoked,
            )

        return self.crud.update(db_session, developer, internal_updater)


developer_service = DeveloperService()
