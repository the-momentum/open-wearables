from uuid import UUID

from fastapi import APIRouter

from app.database import DbSession
from app.repositories import UserConnectionRepository
from app.schemas import UserConnectionRead
from app.services import ApiKeyDep

router = APIRouter()
connection_repo = UserConnectionRepository()


@router.get("/users/{user_id}/connections", response_model=list[UserConnectionRead])
async def get_connections_endpoint(
    user_id: str,
    db: DbSession,
    _api_key: ApiKeyDep,
):
    """Get all connections for a user."""
    connections = connection_repo.get_by_user_id(db, UUID(user_id))
    return [UserConnectionRead.model_validate(conn) for conn in connections]
