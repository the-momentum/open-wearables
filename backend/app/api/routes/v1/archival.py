"""API endpoints for data lifecycle / archival settings.

Admin-only endpoints to configure when live time-series data is archived
(aggregated into daily rows) and when old data is permanently deleted.
"""

from logging import getLogger

from fastapi import APIRouter, status

from app.database import DbSession
from app.integrations.celery.tasks.archival_task import run_daily_archival
from app.schemas.archival import ArchivalSettingUpdate, ArchivalSettingWithEstimate
from app.services import DeveloperDep
from app.services.archival_service import archival_service

router = APIRouter()
logger = getLogger(__name__)


@router.get(
    "/settings/archival",
    status_code=status.HTTP_200_OK,
    summary="Get data lifecycle settings",
    description="Returns current archival/retention configuration and storage size estimates.",
)
async def get_archival_settings(
    db: DbSession,
    _developer: DeveloperDep,
) -> ArchivalSettingWithEstimate:
    return archival_service.get_settings(db)


@router.put(
    "/settings/archival",
    status_code=status.HTTP_200_OK,
    summary="Update data lifecycle settings",
    description=(
        "Configure archive_after_days (when live data is aggregated) and "
        "delete_after_days (when old data is permanently removed). "
        "Set to null to disable."
    ),
)
async def update_archival_settings(
    db: DbSession,
    _developer: DeveloperDep,
    update: ArchivalSettingUpdate,
) -> ArchivalSettingWithEstimate:
    return archival_service.update_settings(db, update)


@router.post(
    "/settings/archival/run",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger archival job manually",
    description="Dispatches the daily archival + retention job via Celery. Returns immediately with the task ID.",
)
async def trigger_archival(
    _developer: DeveloperDep,
) -> dict[str, str]:
    result = run_daily_archival.delay()
    return {"task_id": result.id, "status": "dispatched"}
