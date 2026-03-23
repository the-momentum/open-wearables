from uuid import UUID

from fastapi import APIRouter, Response, status

from app.database import DbSession
from app.schemas.enums import ProviderName
from app.schemas.model_crud.user_management import UserConnectionRead
from app.services import ApiKeyDep
from app.services.providers.factory import ProviderFactory
from app.services.user_connection_service import user_connection_service

router = APIRouter()


@router.get("/users/{user_id}/connections", response_model=list[UserConnectionRead])
def get_connections_endpoint(
    user_id: str,
    db: DbSession,
    _api_key: ApiKeyDep,
):
    """Get all connections for a user."""
    return user_connection_service.get_connections_by_user(db, UUID(user_id))


@router.delete("/users/{user_id}/connections/{provider}")
def disconnect_provider_endpoint(
    user_id: str,
    provider: ProviderName,
    db: DbSession,
    _api_key: ApiKeyDep,
) -> Response:
    """Disconnect a user from a provider, revoking the connection and clearing tokens."""
    strategy = ProviderFactory().get_provider(provider.value)
    user_connection_service.disconnect(db, UUID(user_id), provider.value, oauth=strategy.oauth)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
