from uuid import UUID, uuid4

from sqlalchemy import and_
from sqlalchemy.sql.elements import ColumnElement

from app.database import DbSession
from app.models import ExternalDeviceMapping
from app.repositories.repositories import CrudRepository
from app.schemas.external_mapping import ExternalMappingCreate, ExternalMappingUpdate


class ExternalMappingRepository(
    CrudRepository[ExternalDeviceMapping, ExternalMappingCreate, ExternalMappingUpdate],
):
    """Repository responsible for managing reusable external identifier mappings."""

    def __init__(self, model: type[ExternalDeviceMapping]):
        super().__init__(model)

    def _build_identity_filter(
        self,
        user_id: UUID,
        provider_name: str,
        device_id: str | None,
    ) -> ColumnElement[bool]:
        return and_(
            self.model.user_id == user_id,
            self.model.provider_name == provider_name,
            self.model.device_id == device_id,
        )

    def get_by_identity(
        self,
        db_session: DbSession,
        user_id: UUID,
        provider_name: str,
        device_id: str | None,
    ) -> ExternalDeviceMapping | None:
        return (
            db_session.query(self.model)
            .filter(self._build_identity_filter(user_id, provider_name, device_id))
            .one_or_none()
        )

    def ensure_mapping(
        self,
        db_session: DbSession,
        user_id: UUID,
        provider_name: str,
        device_id: str | None,
        mapping_id: UUID | None = None,
    ) -> ExternalDeviceMapping:
        """
        Return the mapping for the provided identifiers, creating it if needed.

        Args:
            db_session: Active database session.
            user_id: Internal user identifier.
            provider_name: Name of the provider.
            device_id: External device identifier.
            mapping_id: Optional mapping identifier to reuse if provided.
        """
        if mapping_id:
            mapping = db_session.query(self.model).filter(self.model.id == mapping_id).one_or_none()
            if mapping:
                return mapping

        if mapping := self.get_by_identity(db_session, user_id, provider_name, device_id):
            return mapping

        create_payload = ExternalMappingCreate(
            id=mapping_id or uuid4(),
            user_id=user_id,
            provider_name=provider_name,
            device_id=device_id,
        )
        return self.create(db_session, create_payload)  # type: ignore[return-value]
