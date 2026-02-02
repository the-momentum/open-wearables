from uuid import UUID, uuid4

from sqlalchemy import and_, asc, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql.elements import ColumnElement

from app.database import DbSession
from app.models import DataSource, ProviderPriority
from app.repositories.provider_priority_repository import ProviderPriorityRepository
from app.repositories.repositories import CrudRepository
from app.schemas.data_source import DataSourceCreate, DataSourceUpdate
from app.schemas.device_type import (
    DeviceType,
    infer_device_type_from_model,
    infer_device_type_from_source_name,
)
from app.schemas.oauth import ProviderName


class DataSourceRepository(
    CrudRepository[DataSource, DataSourceCreate, DataSourceUpdate],
):
    def __init__(self, model: type[DataSource] = DataSource):
        super().__init__(model)

    def _build_identity_filter(
        self,
        user_id: UUID,
        provider: ProviderName,
        device_model: str | None,
        source: str | None,
    ) -> ColumnElement[bool]:
        conditions = [
            self.model.user_id == user_id,
            self.model.provider == provider,
            func.coalesce(self.model.device_model, "") == (device_model or ""),
            func.coalesce(self.model.source, "") == (source or ""),
        ]
        return and_(*conditions)

    def get_by_identity(
        self,
        db_session: DbSession,
        user_id: UUID,
        provider: ProviderName,
        device_model: str | None = None,
        source: str | None = None,
    ) -> DataSource | None:
        return (
            db_session.query(self.model)
            .filter(self._build_identity_filter(user_id, provider, device_model, source))
            .one_or_none()
        )

    def ensure_data_source(
        self,
        db_session: DbSession,
        user_id: UUID,
        provider: ProviderName,
        user_connection_id: UUID | None = None,
        device_model: str | None = None,
        software_version: str | None = None,
        source: str | None = None,
        original_source_name: str | None = None,
    ) -> DataSource:
        existing = self.get_by_identity(db_session, user_id, provider, device_model, source)
        if existing:
            updated = False
            if user_connection_id and existing.user_connection_id is None:
                object.__setattr__(existing, "user_connection_id", user_connection_id)
                updated = True
            if software_version and existing.software_version is None:
                object.__setattr__(existing, "software_version", software_version)
                updated = True
            if original_source_name and existing.original_source_name is None:
                object.__setattr__(existing, "original_source_name", original_source_name)
                updated = True
            if existing.device_type is None:
                device_type = self._infer_device_type(device_model, original_source_name)
                if device_type != DeviceType.UNKNOWN:
                    object.__setattr__(existing, "device_type", device_type.value)
                    updated = True
            if updated:
                db_session.flush()
            return existing

        provider_priority_repo = ProviderPriorityRepository(ProviderPriority)
        provider_priority_repo.ensure_provider_exists(db_session, provider)

        device_type = self._infer_device_type(device_model, original_source_name)

        create_payload = DataSourceCreate(
            id=uuid4(),
            user_id=user_id,
            provider=provider,
            user_connection_id=user_connection_id,
            device_model=device_model,
            software_version=software_version,
            source=source,
            device_type=device_type.value if device_type != DeviceType.UNKNOWN else None,
            original_source_name=original_source_name,
        )
        result = self.create(db_session, create_payload)
        assert result is not None
        return result

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
        provider: ProviderName,
        user_connection_id: UUID | None,
        identities: set[tuple[UUID, str | None, str | None]],
    ) -> dict[tuple[UUID, str | None, str | None], UUID]:
        if not identities:
            return {}

        identities_list = list(identities)

        from sqlalchemy import or_

        conditions = []
        for user_id, device_model, source in identities_list:
            conditions.append(self._build_identity_filter(user_id, provider, device_model, source))

        existing = db_session.query(self.model).filter(or_(*conditions)).all()

        result: dict[tuple[UUID, str | None, str | None], UUID] = {}
        for ds in existing:
            result[(ds.user_id, ds.device_model, ds.source)] = ds.id

        missing = [i for i in identities_list if i not in result]

        if missing:
            values = []
            for user_id, device_model, source in missing:
                device_type = self._infer_device_type(device_model, None)
                values.append(
                    {
                        "id": uuid4(),
                        "user_id": user_id,
                        "provider": provider,
                        "user_connection_id": user_connection_id,
                        "device_model": device_model,
                        "source": source,
                        "device_type": device_type.value if device_type != DeviceType.UNKNOWN else None,
                    }
                )
            stmt = insert(self.model).values(values).on_conflict_do_nothing()
            db_session.execute(stmt)
            db_session.flush()

            conditions = []
            for user_id, device_model, source in missing:
                conditions.append(self._build_identity_filter(user_id, provider, device_model, source))

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
            .order_by(asc(self.model.provider), asc(self.model.device_model))
            .all()
        )

    def infer_provider_from_source(self, source: str | None) -> ProviderName:
        """Infer provider from source string.

        Deprecated: Use ProviderName.from_source_string() directly instead.
        This method is kept for backward compatibility.
        """
        return ProviderName.from_source_string(source)
