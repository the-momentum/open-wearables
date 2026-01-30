from logging import Logger
from uuid import UUID

from app.database import DbSession
from app.models import DataSource, ProviderPriority
from app.repositories import DataSourceRepository, ProviderPriorityRepository
from app.repositories.device_type_priority_repository import DeviceTypePriorityRepository
from app.schemas.data_source import DataSourceListResponse, DataSourceResponse
from app.schemas.device_type import DeviceType
from app.schemas.oauth import ProviderName
from app.schemas.provider_priority import (
    ProviderPriorityBulkUpdate,
    ProviderPriorityListResponse,
    ProviderPriorityResponse,
)
from app.utils.exceptions import handle_exceptions


class PriorityService:
    def __init__(self, log: Logger):
        self.logger = log
        self.priority_repo = ProviderPriorityRepository(ProviderPriority)
        self.device_type_priority_repo = DeviceTypePriorityRepository()
        self.data_source_repo = DataSourceRepository(DataSource)

    @handle_exceptions
    async def get_provider_priorities(
        self,
        db_session: DbSession,
    ) -> ProviderPriorityListResponse:
        priorities = self.priority_repo.get_all_ordered(db_session)
        return ProviderPriorityListResponse(
            items=[ProviderPriorityResponse.model_validate(p) for p in priorities]
        )

    @handle_exceptions
    async def update_provider_priority(
        self,
        db_session: DbSession,
        provider: ProviderName,
        priority: int,
    ) -> ProviderPriorityResponse:
        result = self.priority_repo.upsert(db_session, provider, priority)
        return ProviderPriorityResponse.model_validate(result)

    @handle_exceptions
    async def bulk_update_priorities(
        self,
        db_session: DbSession,
        update: ProviderPriorityBulkUpdate,
    ) -> ProviderPriorityListResponse:
        priorities_tuples = [(p.provider, p.priority) for p in update.priorities]
        results = self.priority_repo.bulk_update(db_session, priorities_tuples)
        return ProviderPriorityListResponse(
            items=[ProviderPriorityResponse.model_validate(p) for p in results]
        )

    @handle_exceptions
    async def get_user_data_sources(
        self,
        db_session: DbSession,
        user_id: UUID,
    ) -> DataSourceListResponse:
        sources = self.data_source_repo.get_user_data_sources(db_session, user_id)
        items = [
            DataSourceResponse(
                id=ds.id,
                user_id=ds.user_id,
                provider=ds.provider,
                user_connection_id=ds.user_connection_id,
                device_model=ds.device_model,
                software_version=ds.software_version,
                source=ds.source,
                device_type=ds.device_type,
                original_source_name=ds.original_source_name,
                display_name=self._build_display_name(ds),
            )
            for ds in sources
        ]
        return DataSourceListResponse(items=items, total=len(items))

    def get_priority_data_source_ids(
        self,
        db_session: DbSession,
        user_id: UUID,
    ) -> list[UUID]:
        """Get data source IDs for a user, ordered by global priority."""
        provider_order = self.priority_repo.get_priority_order(db_session)
        device_type_order = self.device_type_priority_repo.get_priority_order(db_session)
        sources = self.data_source_repo.get_user_data_sources(db_session, user_id)

        if not sources:
            return []

        def sort_key(ds: DataSource) -> tuple[int, int, str]:
            provider_priority = provider_order.get(ds.provider, 99)
            device_type_priority = 99
            if ds.device_type:
                try:
                    dt = DeviceType(ds.device_type)
                    device_type_priority = device_type_order.get(dt, 99)
                except ValueError:
                    pass
            return (provider_priority, device_type_priority, ds.device_model or "")

        sorted_sources = sorted(sources, key=sort_key)
        return [ds.id for ds in sorted_sources]

    def get_best_data_source_id(
        self,
        db_session: DbSession,
        user_id: UUID,
    ) -> UUID | None:
        ids = self.get_priority_data_source_ids(db_session, user_id)
        return ids[0] if ids else None

    def _build_display_name(self, ds: DataSource) -> str:
        parts = []
        if ds.provider:
            parts.append(ds.provider.value.capitalize())
        if ds.device_model:
            from app.constants.devices import APPLE_DEVICE_NAMES
            readable_model = APPLE_DEVICE_NAMES.get(ds.device_model, ds.device_model)
            parts.append(readable_model)
        elif ds.original_source_name:
            parts.append(ds.original_source_name)
        return " - ".join(parts) if parts else "Unknown Source"
