from typing import Annotated

from fastapi import APIRouter, Depends

from app.database import DbSession
from app.schemas import HKWorkoutListResponse, HKWorkoutQueryParams
from app.services import ApiKeyDep, hk_workout_service

router = APIRouter()


@router.get("/users/{user_id}/workouts")
async def get_workouts_endpoint(
    user_id: str,
    db: DbSession,
    _api_key: ApiKeyDep,
    query_params: Annotated[HKWorkoutQueryParams, Depends()],
) -> HKWorkoutListResponse:
    """Get workouts with filtering, sorting, and pagination."""
    return await hk_workout_service.get_workouts_response(db, query_params, user_id)
