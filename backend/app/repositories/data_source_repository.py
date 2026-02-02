from uuid import UUID, uuid4

from sqlalchemy import and_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql.elements import ColumnElement

from app.database import DbSession
from app.models import DataSource
from app.repositories.repositories import CrudRepository
from app.schemas.data_source import DataSourceCreate, DataSourceUpdate


class DataSourceRepository(
    CrudRepository[DataSource, DataSourceCreate, DataSourceUpdate],
):
    """Repository responsible for managing reusable data source mappings."""

    def __init__(self, model: type[DataSource] = DataSource):
        super().__init__(model)

    def _build_identity_filter(
        self,
        user_id: UUID,
        device_model: str | None,
        source: str | None,
    ) -> ColumnElement[bool]:
        """Build filter for unique identity based on user, device_model, and source."""
        conditions = [self.model.user_id == user_id]

        if device_model:
            conditions.append(self.model.device_model == device_model)
        else:
            conditions.append(self.model.device_model.is_(None))

        if source:
            conditions.append(self.model.source == source)
        else:
            conditions.append(self.model.source.is_(None))

        return and_(*conditions)

    def get_by_identity(
        self,
        db_session: DbSession,
        user_id: UUID,
        device_model: str | None = None,
        source: str | None = None,
    ) -> DataSource | None:
        return (
            db_session.query(self.model)
            .filter(self._build_identity_filter(user_id, device_model, source))
            .one_or_none()
        )

    def ensure_data_source(
        self,
        db_session: DbSession,
        user_id: UUID,
        device_model: str | None = None,
        software_version: str | None = None,
        manufacturer: str | None = None,
        source: str | None = None,
        data_source_id: UUID | None = None,
    ) -> DataSource:
        """
        Return the data source for the provided identifiers, creating it if needed.

        Args:
            db_session: Active database session.
            user_id: Internal user identifier.
            device_model: Device model string (e.g., "iPhone10,5", "Forerunner 910XT").
            software_version: Software version string.
            manufacturer: Device manufacturer.
            source: Data source identifier (e.g., "apple_health_sdk", "garmin_connect_api").
            data_source_id: Optional existing data source ID to reuse.
        """
        # If ID provided, try to find existing
        if data_source_id:
            existing = db_session.query(self.model).filter(self.model.id == data_source_id).one_or_none()
            if existing:
                return existing

        # Try to find by identity
        existing = self.get_by_identity(db_session, user_id, device_model, source)
        if existing:
            # Update fields if new info provided
            updated = False
            if software_version is not None and existing.software_version is None:
                object.__setattr__(existing, "software_version", software_version)
                updated = True
            if manufacturer is not None and existing.manufacturer is None:
                object.__setattr__(existing, "manufacturer", manufacturer)
                updated = True
            if updated:
                db_session.flush()
            return existing

        # Create new
        create_payload = DataSourceCreate(
            id=data_source_id or uuid4(),
            user_id=user_id,
            device_model=device_model,
            software_version=software_version,
            manufacturer=manufacturer,
            source=source,
        )
        return self.create(db_session, create_payload)

    def batch_ensure_data_sources(
        self,
        db_session: DbSession,
        identities: set[tuple[UUID, str | None, str | None]],  # (user_id, device_model, source)
    ) -> dict[tuple[UUID, str | None, str | None], UUID]:
        """Batch get or create data sources. Returns map of identity -> data_source_id.

        Uses INSERT ... ON CONFLICT DO NOTHING for efficiency.
        """
        if not identities:
            return {}

        identities_list = list(identities)

        # Step 1: Batch fetch existing
        # Build OR conditions for each identity
        from sqlalchemy import or_

        conditions = []
        for user_id, device_model, source in identities_list:
            conditions.append(self._build_identity_filter(user_id, device_model, source))

        existing = db_session.query(self.model).filter(or_(*conditions)).all()

        result: dict[tuple[UUID, str | None, str | None], UUID] = {}
        for ds in existing:
            result[(ds.user_id, ds.device_model, ds.source)] = ds.id

        # Step 2: Find missing
        missing = [i for i in identities_list if i not in result]

        if missing:
            # Batch insert missing
            values = [
                {
                    "id": uuid4(),
                    "user_id": user_id,
                    "device_model": device_model,
                    "source": source,
                }
                for user_id, device_model, source in missing
            ]
            stmt = insert(self.model).values(values).on_conflict_do_nothing(constraint="uq_data_source_identity")
            db_session.execute(stmt)
            db_session.flush()

            # Re-fetch newly inserted
            conditions = []
            for user_id, device_model, source in missing:
                conditions.append(self._build_identity_filter(user_id, device_model, source))

            newly_inserted = db_session.query(self.model).filter(or_(*conditions)).all()
            for ds in newly_inserted:
                result[(ds.user_id, ds.device_model, ds.source)] = ds.id

        return result
