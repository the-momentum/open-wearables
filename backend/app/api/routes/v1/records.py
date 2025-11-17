from typing import Annotated

from fastapi import APIRouter, Depends

from app.database import DbSession
from app.schemas import HKRecordListResponse, HKRecordQueryParams

from app.services import hk_record_service, ApiKeyDep

router = APIRouter()


@router.get("/users/{user_id}/records", response_model=HKRecordListResponse)
async def get_records_endpoint(
    user_id: str,
    db: DbSession,
    _api_key: ApiKeyDep,
    query_params: Annotated[HKRecordQueryParams, Depends()],
) -> HKRecordListResponse:
    """Get records with filtering, sorting, and pagination."""
    return await hk_record_service.get_records_response(db, query_params, user_id)
