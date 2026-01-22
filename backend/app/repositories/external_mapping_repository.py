from uuid import UUID, uuid4

from sqlalchemy import and_
from sqlalchemy.sql.elements import ColumnElement

from app.database import DbSession
from app.models import ExternalDeviceMapping
from app.repositories.repositories import CrudRepository
from app.schemas.external_mapping import ExternalMappingCreate, ExternalMappingUpdate
from app.schemas.oauth import ProviderName


class ExternalMappingRepository(
    CrudRepository[ExternalDeviceMapping, ExternalMappingCreate, ExternalMappingUpdate],
):
    """Repository responsible for managing reusable external identifier mappings."""

    def __init__(self, model: type[ExternalDeviceMapping]):
        super().__init__(model)

    def _create_without_commit(self, db_session: DbSession, creator: ExternalMappingCreate) -> ExternalDeviceMapping:
        """Create mapping without committing - flush only to get ID."""
        creation_data = creator.model_dump()
        creation = self.model(**creation_data)
        db_session.add(creation)
        db_session.flush()  # Flush to generate ID without committing
        return creation

    def _build_identity_filter(
        self,
        user_id: UUID,
        device_id: UUID | None,
    ) -> ColumnElement[bool]:
        if not device_id:
            return and_(
                self.model.user_id == user_id,
                self.model.device_id.is_(None),
            )
        return and_(
            self.model.user_id == user_id,
            self.model.device_id == device_id,
        )

    def get_by_identity(
        self,
        db_session: DbSession,
        user_id: UUID,
        device_id: UUID | None,
    ) -> ExternalDeviceMapping | None:
        return db_session.query(self.model).filter(self._build_identity_filter(user_id, device_id)).one_or_none()

    def ensure_mapping(
        self,
        db_session: DbSession,
        user_id: UUID,
        device_id: UUID | None,
        source: str,
        device_software_id: UUID | None = None,
        mapping_id: UUID | None = None,
    ) -> ExternalDeviceMapping:
        """
        Return the mapping for the provided identifiers, creating it if needed.

        Args:
            db_session: Active database session.
            user_id: Internal user identifier.
            device_id: External device identifier (UUID), optional.
            source: Provider source (e.g., 'apple', 'garmin').
            device_software_id: External device software identifier (UUID).
            mapping_id: Optional mapping identifier to reuse if provided.
        """
        if mapping_id:
            mapping = db_session.query(self.model).filter(self.model.id == mapping_id).one_or_none()
            if mapping:
                return mapping

        if device_id and (mapping := self.get_by_identity(db_session, user_id, device_id)):
            return mapping

        # Convert string to ProviderName enum
        provider_enum = ProviderName(source.lower())

        create_payload = ExternalMappingCreate(
            id=mapping_id or uuid4(),
            user_id=user_id,
            device_id=device_id,
            device_software_id=device_software_id,
            source=provider_enum,
        )
        return self._create_without_commit(db_session, create_payload)  # type: ignore[return-value]
