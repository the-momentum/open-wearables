from typing import Annotated

from fastapi import APIRouter, Depends

from app.utils.auth_dependencies import get_current_user_id
from app.database import DbSession
from app.schemas import HKWorkoutListResponse, HKWorkoutQueryParams
from app.services import hk_workout_service

router = APIRouter()


@router.get("/workouts", response_model=HKWorkoutListResponse)
async def get_workouts_endpoint(
    db: DbSession,
    user_id: Annotated[str, Depends(get_current_user_id)],
    query_params: HKWorkoutQueryParams = Depends(),
):
    """Get workouts with filtering, sorting, and pagination."""
    return await hk_workout_service.get_workouts_response(db, query_params, user_id)
