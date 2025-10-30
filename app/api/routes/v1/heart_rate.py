from typing import Annotated

from fastapi import APIRouter, Depends

from app.utils.auth_dependencies import get_current_user_id
from app.database import DbSession
from app.schemas import AEHeartRateListResponse, AEHeartRateQueryParams
from app.services import ae_heart_rate_service

router = APIRouter()


@router.get("/heart-rate", response_model=AEHeartRateListResponse)
async def get_heart_rate_endpoint(
    db: DbSession,
    user_id: Annotated[str, Depends(get_current_user_id)],
    query_params: AEHeartRateQueryParams = Depends(),
):
    """Get heart rate data with filtering, sorting, and pagination."""
    return await ae_heart_rate_service.build_heart_rate_full_data_response(db, query_params, user_id)
