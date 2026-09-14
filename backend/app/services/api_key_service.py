import secrets
from logging import Logger, getLogger
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.database import DbSession, SessionLocal
from app.models import ApiKey, Developer
from app.repositories.api_key_repository import ApiKeyRepository
from app.schemas.model_crud.credentials import ApiKeyCreate, ApiKeyUpdate
from app.services.services import AppService
from app.utils.auth import get_current_developer_optional, oauth2_scheme
from app.utils.exceptions import ResourceNotFoundError, handle_exceptions
from app.utils.security import hash_api_key

# Number of leading characters of the raw key kept in clear for display ("sk-" + 7 hex chars).
KEY_PREFIX_LENGTH = 10


class ApiKeyService(AppService[ApiKeyRepository, ApiKey, ApiKeyCreate, ApiKeyUpdate]):
    def __init__(self, log: Logger, **kwargs):
        super().__init__(
            crud_model=ApiKeyRepository,
            model=ApiKey,
            log=log,
            **kwargs,
        )

    def _generate_key_value(self) -> str:
        """Generate random API key with sk- prefix and 32 hex characters."""
        return f"sk-{secrets.token_hex(16)}"

    @handle_exceptions
    def create_api_key(self, db: DbSession, created_by: UUID | None, name: str = "Default") -> tuple[ApiKey, str]:
        """Create an API key.

        Returns:
            Tuple of (ApiKey, raw_key). Only the hash and a short prefix are persisted,
            so the raw key can be shown to the caller exactly once.
        """
        raw_key = self._generate_key_value()
        creator = ApiKeyCreate(
            key_hash=hash_api_key(raw_key),
            key_prefix=raw_key[:KEY_PREFIX_LENGTH],
            name=name,
            created_by=created_by,
        )
        api_key = self.create(db, creator)
        self.logger.debug(f"Created API key {api_key.id} ({api_key.key_prefix}...) by developer {created_by}")
        return api_key, raw_key

    def list_api_keys(self, db: DbSession) -> list[ApiKey]:
        """List all API keys ordered by creation date."""
        keys = self.crud.get_all_ordered(db)
        self.logger.debug(f"Listed {len(keys)} API keys")
        return keys

    @handle_exceptions
    def rotate_api_key(self, db: DbSession, key_id: UUID, created_by: UUID | None) -> tuple[ApiKey, str]:
        """Rotate API key - delete the old one and create a new one with the same name.

        The delete is only flushed, so the commit issued when the replacement is created
        covers both steps. If creating the replacement fails, the old key stays valid.

        Returns:
            Tuple of (new ApiKey, raw_key). The raw key is shown to the caller exactly once.
        """
        if not (old_key := self.get(db, key_id, raise_404=True)):
            raise ResourceNotFoundError(self.name, key_id)
        name = old_key.name
        self.crud.delete_flush(db, old_key)
        try:
            new_key, raw_key = self.create_api_key(db, created_by, name)
        except Exception:
            db.rollback()
            raise
        self.logger.debug(f"Rotated API key {key_id} to {new_key.id}")
        return new_key, raw_key

    @handle_exceptions
    def validate_api_key(self, db: DbSession, key: str) -> ApiKey:
        """Validate the raw API key against stored hashes. Raises 401 if invalid."""
        if not key or not (api_key := self.crud.get_by_hash(db, hash_api_key(key))):
            raise HTTPException(status_code=401, detail="Invalid or missing API key")
        return api_key


api_key_service = ApiKeyService(log=getLogger(__name__))


async def _authenticate(db: Session, developer: Developer | None, api_key: str | None) -> str:
    if developer:
        return str(developer.id)
    if api_key:
        return str(api_key_service.validate_api_key(db, api_key).id)
    raise HTTPException(status_code=401, detail="Authentication required: provide JWT token or API key")


async def _require_api_key(
    db: DbSession,
    developer: Developer | None = Depends(get_current_developer_optional),
    x_open_wearables_api_key: str | None = Header(None, alias="X-Open-Wearables-API-Key"),
) -> str:
    return await _authenticate(db, developer, x_open_wearables_api_key)


async def _require_api_key_detached(
    token: Annotated[str | None, Depends(oauth2_scheme)] = None,
    x_open_wearables_api_key: str | None = Header(None, alias="X-Open-Wearables-API-Key"),
) -> str:
    """Same rule as ApiKeyDep, but on a session released before the endpoint returns.

    DbSession is a yield dependency, so anything that declares it — including the usual auth
    dependency — holds a pooled connection until the response completes. For a stream that is
    until the client disconnects, so a streaming endpoint has to authenticate detached.
    """
    with SessionLocal() as db:
        return await _authenticate(db, await get_current_developer_optional(db, token), x_open_wearables_api_key)


ApiKeyDep = Annotated[str, Depends(_require_api_key)]
StreamingApiKeyDep = Annotated[str, Depends(_require_api_key_detached)]
