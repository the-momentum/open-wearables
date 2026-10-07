"""API endpoints for data lifecycle / archival settings.

Admin-only endpoints to configure when live time-series data is archived
(aggregated into daily rows) and when old data is permanently deleted.
"""

from logging import getLogger

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import settings
from app.database import DbSession
from app.integrations.celery.tasks.archival_task import run_daily_archival
from app.schemas.utils import ArchivalSettingUpdate, ArchivalSettingWithEstimate
from app.services import DeveloperDep
from app.services.archival_service import archival_service

logger = getLogger(__name__)


def _require_data_lifecycle_enabled(_developer: DeveloperDep) -> None:
    if not settings.data_lifecycle_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Data lifecycle is not enabled (set DATA_LIFECYCLE_ENABLED=true in the backend environment).",
        )


router = APIRouter(dependencies=[Depends(_require_data_lifecycle_enabled)])


@router.get(
    "/settings/archival",
    summary="Get data lifecycle settings",
    description="Returns current archival/retention configuration and storage size estimates.",
)
def get_archival_settings(
    db: DbSession,
    _developer: DeveloperDep,
) -> ArchivalSettingWithEstimate:
    return archival_service.get_settings(db)


@router.put(
    "/settings/archival",
    summary="Update data lifecycle settings",
    description=(
        "Configure archive_after_days (when live data is aggregated) and "
        "delete_after_days (when old data is permanently removed). "
        "Set to null to disable."
    ),
)
def update_archival_settings(
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
def trigger_archival(
    _developer: DeveloperDep,
) -> dict[str, str]:
    result = run_daily_archival.delay()
    return {"task_id": result.id, "status": "dispatched"}
