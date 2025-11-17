from typing import Annotated

from fastapi import APIRouter, Depends

from app.database import DbSession
from app.schemas import AEHeartRateListResponse, AEHeartRateQueryParams

from app.services import ae_heart_rate_service, ApiKeyDep

router = APIRouter()



@router.get("/users/{user_id}/heart-rate", response_model=AEHeartRateListResponse)
async def get_heart_rate_endpoint(
    user_id: str,
    db: DbSession,
    _api_key: ApiKeyDep,
    query_params: Annotated[AEHeartRateQueryParams, Depends()],
) -> AEHeartRateListResponse:
    """Get heart rate data with filtering, sorting, and pagination."""
    return await ae_heart_rate_service.build_heart_rate_full_data_response(db, query_params, user_id)
