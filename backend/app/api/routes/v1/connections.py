import logging
from uuid import UUID

from fastapi import APIRouter, Response, status

from app.database import DbSession
from app.repositories import UserConnectionRepository
from app.schemas import ConnectionStatus, UserConnectionRead
from app.schemas.oauth import ProviderName
from app.services import ApiKeyDep

logger = logging.getLogger(__name__)

router = APIRouter()
connection_repo = UserConnectionRepository()


@router.get("/users/{user_id}/connections", response_model=list[UserConnectionRead])
def get_connections_endpoint(
    user_id: str,
    db: DbSession,
    _api_key: ApiKeyDep,
):
    """Get all connections for a user."""
    connections = connection_repo.get_by_user_id(db, UUID(user_id))
    return [UserConnectionRead.model_validate(conn) for conn in connections]


@router.delete("/users/{user_id}/connections/{provider}", status_code=status.HTTP_204_NO_CONTENT)
def disconnect_provider_endpoint(
    user_id: str,
    provider: ProviderName,
    db: DbSession,
    _api_key: ApiKeyDep,
) -> Response:
    """Disconnect a user from a provider, revoking the connection and clearing tokens."""
    connection = connection_repo.get_by_user_and_provider(db, UUID(user_id), provider.value)

    if connection is None or connection.status == ConnectionStatus.REVOKED:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    connection_repo.disconnect(db, connection)
    logger.info("Disconnected user %s from provider %s", user_id, provider.value)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
