from typing import Annotated

from fastapi import APIRouter, Depends

from app.database import DbSession
from app.schemas import EventRecordQueryParams, EventRecordResponse
from app.services import ApiKeyDep, event_record_service

router = APIRouter()


@router.get("/users/{user_id}/workouts", response_model=list[EventRecordResponse])
async def get_workouts_endpoint(
    user_id: str,
    db: DbSession,
    _api_key: ApiKeyDep,
    query_params: Annotated[EventRecordQueryParams, Depends()],
):
    """Get workouts with filtering, sorting, and pagination."""
    return await event_record_service.get_records_response(db, query_params, user_id)
