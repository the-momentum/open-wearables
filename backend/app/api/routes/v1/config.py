from fastapi import APIRouter, status

from app.database import DbSession
from app.integrations.celery.tasks.archival_task import run_daily_archival
from app.schemas.app_config import RESTART_REQUIRED_KEYS, AppConfigResponse, AppConfigUpdate
from app.schemas.utils import StorageEstimate, TaskDispatchResponse
from app.services import DeveloperDep
from app.services.archival_service import archival_service
from app.services.config_service import config_service

router = APIRouter()

_RESTART_REQUIRED_FIELDS = sorted(RESTART_REQUIRED_KEYS)


@router.get(
    "/config",
    status_code=status.HTTP_200_OK,
    summary="Get application config",
    description="Effective runtime config (DB value, else the config.py default) for the admin panel.",
)
def get_config(_developer: DeveloperDep) -> AppConfigResponse:
    return AppConfigResponse(config=config_service.get(), restart_required_fields=_RESTART_REQUIRED_FIELDS)


@router.put(
    "/config",
    status_code=status.HTTP_200_OK,
    summary="Update application config",
    description=(
        "Persists the provided fields and invalidates the shared config cache so all "
        "processes pick them up. Fields in restart_required_fields only take effect after "
        "a container restart."
    ),
)
def update_config(_developer: DeveloperDep, update: AppConfigUpdate) -> AppConfigResponse:
    return AppConfigResponse(config=config_service.update(update), restart_required_fields=_RESTART_REQUIRED_FIELDS)


@router.get(
    "/config/storage",
    status_code=status.HTTP_200_OK,
    summary="Get storage estimate",
    description="Table-size estimates and growth projection (drives the data-lifecycle UI).",
)
def get_storage(db: DbSession, _developer: DeveloperDep) -> StorageEstimate:
    return archival_service.get_storage(db)


@router.post(
    "/config/archival/run",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger archival job manually",
    description="Dispatches the daily archival + retention job via Celery. Returns the task ID.",
)
def trigger_archival(_developer: DeveloperDep) -> TaskDispatchResponse:
    result = run_daily_archival.delay()
    return TaskDispatchResponse(task_id=result.id, status="dispatched")
