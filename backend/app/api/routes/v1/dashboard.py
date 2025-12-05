from fastapi import APIRouter

from app.database import DbSession
from app.schemas.system_info import SystemInfoResponse
from app.services import DeveloperDep, system_info_service

router = APIRouter()


@router.get("/system-info", response_model=SystemInfoResponse, tags=["dashboard"])
async def get_system_info(db: DbSession, _developer: DeveloperDep):
    """Get system dashboard information."""
    return system_info_service.get_system_info(db)
