from typing import Annotated

from fastapi import APIRouter, Depends

from app.database import DbSession
from app.services import ApiKeyDep, workout_statistic_service
from app.schemas import WorkoutStatisticQueryParams
from app.models import WorkoutStatistic

router = APIRouter()


@router.get("/users/{user_id}/heart-rate")
async def get_heart_rate_endpoint(
    user_id: str,
    db: DbSession,
    _api_key: ApiKeyDep,
    query_params: Annotated[WorkoutStatisticQueryParams, Depends()],
) -> list[WorkoutStatistic]:
    """Get heart rate data with filtering, sorting, and pagination."""
    return await workout_statistic_service.get_heart_rate_statistics(db, query_params, user_id)
