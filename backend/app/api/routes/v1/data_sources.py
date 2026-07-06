"""API endpoints for user data sources."""

from logging import getLogger
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path

from app.database import DbSession
from app.schemas.model_crud.data_priority import DataSourceListResponse
from app.services import ApiKeyDep, PriorityService

router = APIRouter()
priority_service = PriorityService(log=getLogger(__name__))


@router.get(
    "/users/{user_id}/data-sources",
    summary="Get user data sources",
)
def get_user_data_sources(
    db: DbSession,
    _api_key: ApiKeyDep,
    user_id: Annotated[UUID, Path(description="User ID")],
) -> DataSourceListResponse:
    return priority_service.get_user_data_sources(db, user_id)
