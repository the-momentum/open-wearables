"""The instance's identity: public info for apps and the settings an administrator edits."""

from fastapi import APIRouter

from app.database import DbSession
from app.schemas.model_crud.instance_settings import InstanceInfo, InstanceSettingsRead, InstanceSettingsUpdate
from app.services import DeveloperDep
from app.services.instance_service import instance_service

router = APIRouter()
settings_router = APIRouter()


@router.get("/info")
def get_instance_info(db: DbSession) -> InstanceInfo:
    """Who runs this instance, for an app to show before a user connects.

    Public: an app calls it with nothing but the server address from an invitation,
    and a dashboard address typed by mistake fails here instead of at redeem.
    """
    return instance_service.get_info(db)


@settings_router.get("/settings")
def get_instance_settings(db: DbSession, _developer: DeveloperDep) -> InstanceSettingsRead:
    return instance_service.get_settings(db)


@settings_router.patch("/settings")
def update_instance_settings(
    payload: InstanceSettingsUpdate, db: DbSession, _developer: DeveloperDep
) -> InstanceSettingsRead:
    return instance_service.update_settings(db, payload)
