from typing import Annotated

from fastapi import APIRouter, Depends

from app.database import DbSession
from app.schemas import HeartRateSampleResponse, TimeSeriesQueryParams
from app.services import ApiKeyDep, time_series_service

router = APIRouter()


@router.get("/users/{user_id}/heart-rate", response_model=list[HeartRateSampleResponse])
async def get_heart_rate_endpoint(
    user_id: str,
    db: DbSession,
    _api_key: ApiKeyDep,
    query_params: Annotated[TimeSeriesQueryParams, Depends()],
):
    """Get heart rate data with filtering, sorting, and pagination."""
    return await time_series_service.get_user_heart_rate_series(db, user_id, query_params)
