"""API endpoints for managing global provider priorities and user data sources."""

from logging import getLogger
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path

from app.database import DbSession
from app.schemas.data_source import DataSourceListResponse
from app.schemas.device_type import DeviceType
from app.schemas.device_type_priority import (
    DeviceTypePriorityBulkUpdate,
    DeviceTypePriorityListResponse,
    DeviceTypePriorityResponse,
    DeviceTypePriorityUpdate,
)
from app.schemas.oauth import ProviderName
from app.schemas.provider_priority import (
    ProviderPriorityBulkUpdate,
    ProviderPriorityListResponse,
    ProviderPriorityResponse,
    ProviderPriorityUpdate,
)
from app.services import ApiKeyDep, DeveloperDep, PriorityService

router = APIRouter()
priority_service = PriorityService(log=getLogger(__name__))


@router.get(
    "/priorities/providers",
    summary="Get global provider priorities",
)
async def get_provider_priorities(
    db: DbSession,
    _developer: DeveloperDep,
) -> ProviderPriorityListResponse:
    return await priority_service.get_provider_priorities(db)


@router.put(
    "/priorities/providers/{provider}",
    summary="Update provider priority",
)
async def update_provider_priority(
    db: DbSession,
    _developer: DeveloperDep,
    provider: Annotated[ProviderName, Path(description="Provider name enum")],
    update: ProviderPriorityUpdate,
) -> ProviderPriorityResponse:
    return await priority_service.update_provider_priority(db, provider, update.priority)


@router.put(
    "/priorities/providers",
    summary="Bulk update provider priorities",
)
async def bulk_update_provider_priorities(
    db: DbSession,
    _developer: DeveloperDep,
    update: ProviderPriorityBulkUpdate,
) -> ProviderPriorityListResponse:
    return await priority_service.bulk_update_priorities(db, update)


@router.get(
    "/users/{user_id}/data-sources",
    summary="Get user data sources",
)
async def get_user_data_sources(
    db: DbSession,
    _api_key: ApiKeyDep,
    user_id: Annotated[UUID, Path(description="User ID")],
) -> DataSourceListResponse:
    return await priority_service.get_user_data_sources(db, user_id)


@router.get(
    "/priorities/device-types",
    summary="Get device type priorities",
)
async def get_device_type_priorities(
    db: DbSession,
    _developer: DeveloperDep,
) -> DeviceTypePriorityListResponse:
    return await priority_service.get_device_type_priorities(db)


@router.put(
    "/priorities/device-types/{device_type}",
    summary="Update device type priority",
)
async def update_device_type_priority(
    db: DbSession,
    _developer: DeveloperDep,
    device_type: Annotated[DeviceType, Path(description="Device type enum")],
    update: DeviceTypePriorityUpdate,
) -> DeviceTypePriorityResponse:
    return await priority_service.update_device_type_priority(db, device_type, update.priority)


@router.put(
    "/priorities/device-types",
    summary="Bulk update device type priorities",
)
async def bulk_update_device_type_priorities(
    db: DbSession,
    _developer: DeveloperDep,
    update: DeviceTypePriorityBulkUpdate,
) -> DeviceTypePriorityListResponse:
    return await priority_service.bulk_update_device_type_priorities(db, update)
