from app import __version__ as core_version
from app.database import DbSession
from app.repositories.instance_settings_repository import InstanceSettingsRepository
from app.schemas.model_crud.instance_settings import InstanceInfo, InstanceSettingsRead, InstanceSettingsUpdate
from app.services.app_registration_service import app_registration_service
from app.utils.exceptions import InvalidInputError
from app.utils.structured_logging import get_logger

logger = get_logger(__name__)

# A change to either of these is a new version of the documents users accept.
_DOCUMENT_FIELDS = ("privacy_policy_url", "terms_url")


class InstanceService:
    """The instance's own identity: the settings an administrator edits and the public info apps read."""

    def __init__(self) -> None:
        self.repo = InstanceSettingsRepository()

    def get_settings(self, db: DbSession) -> InstanceSettingsRead:
        settings = self.repo.get(db)
        return InstanceSettingsRead.model_validate(settings) if settings else InstanceSettingsRead()

    def update_settings(self, db: DbSession, update: InstanceSettingsUpdate) -> InstanceSettingsRead:
        changes = update.model_dump(mode="json", exclude_unset=True, exclude={"bump_legal_documents_version"})
        if changes.get("require_acceptance", ...) is None:
            changes.pop("require_acceptance")  # null means "leave as is" for a flag
        current = self.get_settings(db)
        after = current.model_copy(update=changes)
        if after.require_acceptance and not (after.privacy_policy_url or after.terms_url):
            raise InvalidInputError("Set a privacy policy or terms URL before requiring users to accept them")
        documents_changed = any(
            field in changes and changes[field] != getattr(current, field) for field in _DOCUMENT_FIELDS
        )
        if documents_changed or update.bump_legal_documents_version:
            changes["legal_documents_version"] = current.legal_documents_version + 1
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
            privacy_policy_url=settings.privacy_policy_url,
            terms_url=settings.terms_url,
            require_acceptance=settings.require_acceptance,
            legal_documents_version=settings.legal_documents_version,
        )


instance_service = InstanceService()
