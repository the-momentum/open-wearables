from uuid import UUID, uuid4

from sqlalchemy import and_, asc
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql.elements import ColumnElement

from app.database import DbSession
from app.models import DataSource
from app.repositories.repositories import CrudRepository
from app.schemas.data_source import DataSourceCreate, DataSourceUpdate
from app.schemas.device_type import (
    DeviceType,
    infer_device_type_from_model,
    infer_device_type_from_source_name,
)


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
        source: str | None = None,
        data_source_id: UUID | None = None,
        original_source_name: str | None = None,
    ) -> DataSource:
        if data_source_id:
            existing = db_session.query(self.model).filter(self.model.id == data_source_id).one_or_none()
            if existing:
                return existing

        existing = self.get_by_identity(db_session, user_id, device_model, source)
        if existing:
            updated = False
            if software_version is not None and existing.software_version is None:
                object.__setattr__(existing, "software_version", software_version)
                updated = True
            if original_source_name is not None and existing.original_source_name is None:
                object.__setattr__(existing, "original_source_name", original_source_name)
                updated = True
            # Infer device_type if not set
            if existing.device_type is None:
                device_type = self._infer_device_type(device_model, original_source_name)
                if device_type != DeviceType.UNKNOWN:
                    object.__setattr__(existing, "device_type", device_type.value)
                    updated = True
            if updated:
                db_session.flush()
            return existing

        device_type = self._infer_device_type(device_model, original_source_name)

        create_payload = DataSourceCreate(
            id=data_source_id or uuid4(),
            user_id=user_id,
            device_model=device_model,
            software_version=software_version,
            source=source,
            device_type=device_type.value if device_type != DeviceType.UNKNOWN else None,
            original_source_name=original_source_name,
        )
        return self.create(db_session, create_payload)

    def _infer_device_type(
        self,
        device_model: str | None,
        original_source_name: str | None,
    ) -> DeviceType:
        dt = infer_device_type_from_model(device_model)
        if dt != DeviceType.UNKNOWN:
            return dt
        return infer_device_type_from_source_name(original_source_name)

    def batch_ensure_data_sources(
        self,
        db_session: DbSession,
        identities: set[tuple[UUID, str | None, str | None]],
    ) -> dict[tuple[UUID, str | None, str | None], UUID]:
        if not identities:
            return {}

        identities_list = list(identities)

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
            values = []
            for user_id, device_model, source in missing:
                device_type = self._infer_device_type(device_model, None)
                values.append(
                    {
                        "id": uuid4(),
                        "user_id": user_id,
                        "device_model": device_model,
                        "source": source,
                        "device_type": device_type.value if device_type != DeviceType.UNKNOWN else None,
                    }
                )
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

    def get_user_data_sources(
        self,
        db_session: DbSession,
        user_id: UUID,
    ) -> list[DataSource]:
        return (
            db_session.query(self.model)
            .filter(self.model.user_id == user_id)
            .order_by(asc(self.model.source), asc(self.model.device_model))
            .all()
        )

    def get_provider_from_source(self, source: str | None) -> str | None:
        if not source:
            return None

        provider_map = {
            "apple": ["apple_health", "apple_xml", "apple_auto_export"],
            "garmin": ["garmin_connect", "garmin_api"],
            "suunto": ["suunto_api", "suunto"],
            "polar": ["polar_api", "polar"],
            "whoop": ["whoop_api", "whoop"],
            "oura": ["oura_api", "oura"],
        }

        source_lower = source.lower()
        for provider, patterns in provider_map.items():
            if any(pattern in source_lower for pattern in patterns):
                return provider

        return source.split("_")[0] if "_" in source else source
