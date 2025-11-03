from typing import Annotated

from fastapi import APIRouter, Depends

from app.utils.auth_dependencies import get_current_user_id
from app.database import DbSession
from app.schemas import HKRecordListResponse, HKRecordQueryParams
from app.services import hk_record_service

router = APIRouter()


@router.get("/records", response_model=HKRecordListResponse)
async def get_records_endpoint(
    db: DbSession,
    user_id: Annotated[str, Depends(get_current_user_id)],
    query_params: HKRecordQueryParams = Depends(),
):
    """Get records with filtering, sorting, and pagination."""
    return await hk_record_service.get_records_response(db, query_params, user_id)
