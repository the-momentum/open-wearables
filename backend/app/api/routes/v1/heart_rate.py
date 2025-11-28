from fastapi import APIRouter

from app.database import DbSession
from app.services import ApiKeyDep, workout_statistic_service
from app.schemas import WorkoutStatisticResponse

router = APIRouter()


@router.get("/users/{user_id}/heart-rate")
async def get_heart_rate_endpoint(
    user_id: str,
    db: DbSession,
    _api_key: ApiKeyDep,
) -> list[WorkoutStatisticResponse]:
    """Get heart rate data with filtering, sorting, and pagination."""
    return await workout_statistic_service.get_user_heart_rate_statistics(db, user_id)
