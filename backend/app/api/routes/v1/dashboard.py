from typing import Annotated

from fastapi import APIRouter, Query

from app.database import DbSession
from app.schemas.responses.upload import SystemInfoResponse
from app.services import DeveloperDep, system_info_service

router = APIRouter()


@router.get("/stats", response_model=SystemInfoResponse, tags=["dashboard"])
def get_stats(
    db: DbSession,
    _developer: DeveloperDep,
    top_limit: Annotated[
        int, Query(ge=1, le=20, description="Number of top items to return for series types and workout types")
    ] = 6,
):
    """Get system dashboard statistics."""
    return system_info_service.get_system_info(db, top_limit=top_limit)
