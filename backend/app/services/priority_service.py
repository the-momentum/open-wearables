from uuid import UUID

from celery import current_app as celery_app

from app.constants.celery_tasks import CeleryTask
from app.constants.devices_map import resolve_device_name
from app.database import DbSession
from app.models import DataSource, ProviderPriority
from app.repositories import DataSourceRepository, ProviderPriorityRepository
from app.repositories.device_type_priority_repository import DeviceTypePriorityRepository
from app.repositories.repositories import SourceRanking
from app.schemas.enums import DeviceType, ProviderName
from app.schemas.model_crud.data_priority import (
    DataSourceListResponse,
    DataSourceResponse,
    DeviceTypePriorityBulkUpdate,
    DeviceTypePriorityListResponse,
    DeviceTypePriorityResponse,
    ProviderPriorityBulkUpdate,
    ProviderPriorityListResponse,
    ProviderPriorityResponse,
)
from app.utils.structured_logging import get_logger

logger = get_logger(__name__)


class PriorityService:
    def __init__(self):
        self.priority_repo = ProviderPriorityRepository(ProviderPriority)
        self.device_type_priority_repo = DeviceTypePriorityRepository()
        self.data_source_repo = DataSourceRepository(DataSource)

    def get_source_ranking(self, db_session: DbSession) -> SourceRanking:
        """The provider and device type priorities as configured now, to rank a user's data sources by."""
        return SourceRanking(
            self.priority_repo.get_priority_order(db_session),
            self.device_type_priority_repo.get_priority_order(db_session),
        )

    def _to_provider_response(self, priority: ProviderPriority) -> ProviderPriorityResponse:
        # The display name and icon are added by the priorities routes: the provider strategies they come from
        # import the services that read get_source_ranking, so importing them here would be circular.
        return ProviderPriorityResponse.model_validate(priority)

    def get_provider_priorities(
        self,
        db_session: DbSession,
    ) -> ProviderPriorityListResponse:
        priorities = self.priority_repo.get_all_ordered(db_session)
        return ProviderPriorityListResponse(items=[self._to_provider_response(p) for p in priorities])

    def update_provider_priority(
        self,
        db_session: DbSession,
        provider: ProviderName,
        priority: int,
    ) -> ProviderPriorityResponse:
        result = self.priority_repo.upsert(db_session, provider, priority)
        db_session.commit()
        _drop_reconciled_days()
        return self._to_provider_response(result)

    def bulk_update_priorities(
        self,
        db_session: DbSession,
        update: ProviderPriorityBulkUpdate,
    ) -> ProviderPriorityListResponse:
        priorities_tuples = [(p.provider, p.priority) for p in update.priorities]
        results = self.priority_repo.bulk_update(db_session, priorities_tuples)
        db_session.commit()
        _drop_reconciled_days()
        return ProviderPriorityListResponse(items=[self._to_provider_response(p) for p in results])

    def get_user_data_sources(
        self,
        db_session: DbSession,
        user_id: UUID,
    ) -> DataSourceListResponse:
        sources = self.data_source_repo.get_user_data_sources(db_session, user_id)
        items = [self._to_data_source_response(ds) for ds in sources]
        return DataSourceListResponse(items=items, total=len(items))

    def _to_data_source_response(self, ds: DataSource) -> DataSourceResponse:
        device_name = resolve_device_name(ds.device_model)
        return DataSourceResponse(
            id=ds.id,
            user_id=ds.user_id,
            provider=ds.provider,
            user_connection_id=ds.user_connection_id,
            device_model=ds.device_model,
            software_version=ds.software_version,
            source=ds.source,
            device_type=ds.device_type,
            original_source_name=ds.original_source_name,
            device_name=device_name,
            display_name=self._build_display_name(ds, device_name),
        )

    def get_device_type_priorities(
        self,
        db_session: DbSession,
    ) -> DeviceTypePriorityListResponse:
        priorities = self.device_type_priority_repo.get_all_ordered(db_session)
        return DeviceTypePriorityListResponse(items=[DeviceTypePriorityResponse.model_validate(p) for p in priorities])

    def update_device_type_priority(
        self,
        db_session: DbSession,
        device_type: DeviceType,
        priority: int,
    ) -> DeviceTypePriorityResponse:
        result = self.device_type_priority_repo.upsert(db_session, device_type, priority)
        db_session.commit()
        _drop_reconciled_days()
        return DeviceTypePriorityResponse.model_validate(result)

    def bulk_update_device_type_priorities(
        self,
        db_session: DbSession,
        update: DeviceTypePriorityBulkUpdate,
    ) -> DeviceTypePriorityListResponse:
        priorities_tuples = [(p.device_type, p.priority) for p in update.priorities]
        results = self.device_type_priority_repo.bulk_update(db_session, priorities_tuples)
        db_session.commit()
        _drop_reconciled_days()
        return DeviceTypePriorityListResponse(items=[DeviceTypePriorityResponse.model_validate(p) for p in results])

    def _build_display_name(self, ds: DataSource, device_name: str | None) -> str:
        parts = []
        if ds.provider:
            # Rows loaded from the database carry provider as a plain str (the
            # column is a String, not a native enum), so there is no .value.
            parts.append(ds.provider.capitalize())
        if device_name:
            parts.append(device_name)
        elif ds.original_source_name:
            parts.append(ds.original_source_name)
        return " - ".join(parts) if parts else "Unknown Source"


priority_service = PriorityService()


def _drop_reconciled_days() -> None:
    """Merged days stored in the old order are dropped in the background, so reads merge them in the new one."""
    try:
        celery_app.send_task(CeleryTask.DROP_RECONCILED_DAYS, retry=False)
    except Exception as exc:
        # Reads keep the stale merge until the next priority change; nothing else depends on this.
        logger.warning("Could not queue dropping merged days after a priority change", exc_info=exc)
