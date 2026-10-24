from app import __version__ as core_version
from app.database import DbSession
from app.repositories.instance_settings_repository import InstanceSettingsRepository
from app.schemas.model_crud.instance_settings import InstanceInfo, InstanceSettingsRead, InstanceSettingsUpdate
from app.services.app_registration_service import app_registration_service
from app.utils.structured_logging import get_logger

logger = get_logger(__name__)


class InstanceService:
    """The instance's own identity: the settings an administrator edits and the public info apps read."""

    def __init__(self) -> None:
        self.repo = InstanceSettingsRepository()

    def get_settings(self, db: DbSession) -> InstanceSettingsRead:
        settings = self.repo.get(db)
        return InstanceSettingsRead.model_validate(settings) if settings else InstanceSettingsRead()

    def update_settings(self, db: DbSession, update: InstanceSettingsUpdate) -> InstanceSettingsRead:
        changes = update.model_dump(mode="json", exclude_unset=True)
        settings = self.repo.update(db, changes)
        logger.info("Instance settings updated", fields=sorted(changes))
        return InstanceSettingsRead.model_validate(settings)

    def get_info(self, db: DbSession) -> InstanceInfo:
        settings = self.get_settings(db)
        app_enabled, instance_id = app_registration_service.app_identity(db)
        return InstanceInfo(
            name=settings.organization_name,
            logo_url=settings.logo_url,
            support_email=settings.support_email,
            api_version=core_version,
            app_enabled=app_enabled,
            instance_id=instance_id,
        )


instance_service = InstanceService()
