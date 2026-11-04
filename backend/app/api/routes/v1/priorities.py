"""API endpoints for managing global provider priorities."""

import contextlib
from typing import Annotated

from fastapi import APIRouter, Path

from app.database import DbSession
from app.schemas.enums import DeviceType, ProviderName
from app.schemas.model_crud.data_priority import (
    DeviceTypePriorityBulkUpdate,
    DeviceTypePriorityListResponse,
    DeviceTypePriorityResponse,
    DeviceTypePriorityUpdate,
    ProviderPriorityBulkUpdate,
    ProviderPriorityListResponse,
    ProviderPriorityResponse,
    ProviderPriorityUpdate,
)
from app.services import DeveloperDep, PriorityService
from app.services.providers.factory import ProviderFactory

router = APIRouter()
priority_service = PriorityService()


def _with_display(item: ProviderPriorityResponse) -> ProviderPriorityResponse:
    """The strategy's display name and icon, as provider settings show them. Added here, not in the priority
    service: the strategies import the services that rank sources through it, a circular import there."""
    with contextlib.suppress(ValueError):
        strategy = ProviderFactory().get_provider(ProviderName(item.provider).value)
        item.name, item.icon_url = strategy.display_name, strategy.icon_url
    return item


@router.get(
    "/priorities/providers",
    summary="Get global provider priorities",
)
def get_provider_priorities(
    db: DbSession,
    _developer: DeveloperDep,
) -> ProviderPriorityListResponse:
    result = priority_service.get_provider_priorities(db)
    result.items = [_with_display(item) for item in result.items]
    return result


@router.put(
    "/priorities/providers/{provider}",
    summary="Update provider priority",
)
def update_provider_priority(
    db: DbSession,
    _developer: DeveloperDep,
    provider: Annotated[ProviderName, Path(description="Provider name enum")],
    update: ProviderPriorityUpdate,
) -> ProviderPriorityResponse:
    return _with_display(priority_service.update_provider_priority(db, provider, update.priority))


@router.put(
    "/priorities/providers",
    summary="Bulk update provider priorities",
)
def bulk_update_provider_priorities(
    db: DbSession,
    _developer: DeveloperDep,
    update: ProviderPriorityBulkUpdate,
) -> ProviderPriorityListResponse:
    result = priority_service.bulk_update_priorities(db, update)
    result.items = [_with_display(item) for item in result.items]
    return result


@router.get(
    "/priorities/device-types",
    summary="Get device type priorities",
)
def get_device_type_priorities(
    db: DbSession,
    _developer: DeveloperDep,
) -> DeviceTypePriorityListResponse:
    return priority_service.get_device_type_priorities(db)


@router.put(
    "/priorities/device-types/{device_type}",
    summary="Update device type priority",
)
def update_device_type_priority(
    db: DbSession,
    _developer: DeveloperDep,
    device_type: Annotated[DeviceType, Path(description="Device type enum")],
    update: DeviceTypePriorityUpdate,
) -> DeviceTypePriorityResponse:
    return priority_service.update_device_type_priority(db, device_type, update.priority)


@router.put(
    "/priorities/device-types",
    summary="Bulk update device type priorities",
)
def bulk_update_device_type_priorities(
    db: DbSession,
    _developer: DeveloperDep,
    update: DeviceTypePriorityBulkUpdate,
) -> DeviceTypePriorityListResponse:
    return priority_service.bulk_update_device_type_priorities(db, update)
