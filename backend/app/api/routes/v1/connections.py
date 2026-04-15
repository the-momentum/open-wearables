import contextlib
from uuid import UUID

from fastapi import APIRouter, Response, status

from app.database import DbSession
from app.schemas.enums import ProviderName
from app.schemas.model_crud.user_management import UserConnectionWithCapabilities
from app.services import ApiKeyDep, user_connection_service
from app.services.providers.factory import ProviderFactory

router = APIRouter()
factory = ProviderFactory()


def _with_capabilities(conn: object) -> UserConnectionWithCapabilities:
    enriched = UserConnectionWithCapabilities.model_validate(conn)
    with contextlib.suppress(ValueError):
        caps = factory.get_provider(enriched.provider).capabilities
        enriched.max_historical_days = caps.max_historical_days
        enriched.supports_pull = caps.supports_pull
    return enriched


@router.get("/users/{user_id}/connections", response_model=list[UserConnectionWithCapabilities])
def get_connections_endpoint(
    user_id: UUID,
    db: DbSession,
    _api_key: ApiKeyDep,
):
    """Get all connections for a user, enriched with provider capability metadata."""
    return [_with_capabilities(conn) for conn in user_connection_service.get_connections_by_user(db, user_id)]


@router.delete("/users/{user_id}/connections/{provider}")
def disconnect_provider_endpoint(
    user_id: UUID,
    provider: ProviderName,
    db: DbSession,
    _api_key: ApiKeyDep,
) -> Response:
    """Disconnect a user from a provider, revoking the connection and clearing tokens."""
    strategy = ProviderFactory().get_provider(provider.value)
    user_connection_service.disconnect(db, user_id, provider.value, oauth=strategy.oauth)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
