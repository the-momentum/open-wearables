from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from app.config import settings
from app.database import DbSession
from app.models import ApiKey, Developer
from app.repositories.api_key_repository import ApiKeyRepository
from app.repositories.developer_repository import DeveloperRepository
from app.schemas.auth import SDKAuthContext
from app.utils.security import hash_api_key

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)
developer_repository = DeveloperRepository(Developer)
api_key_repository = ApiKeyRepository(ApiKey)


def validate_api_key(db: DbSession, key: str | None) -> ApiKey:
    """Validate the raw API key against stored hashes. Raises 401 if invalid."""
    if not key or not (api_key := api_key_repository.get_by_hash(db, hash_api_key(key))):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return api_key


def get_current_developer(
    db: DbSession,
    token: Annotated[str | None, Depends(oauth2_scheme)],
) -> Developer:
    """Get current authenticated developer from JWT token.

    SDK-scoped tokens are rejected - they can only access /sdk/ endpoints.

    Deliberately ``def``, not ``async def``: the lookup below is a blocking
    driver call, and on the event loop it stalls *every* in-flight request for
    as long as it takes to get a pooled connection — turning a slow query into
    an app-wide freeze. As a sync dependency FastAPI runs it in the threadpool,
    so only this request waits.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        raise credentials_exception

    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])

        # Reject SDK-scoped tokens - they can ONLY access /sdk/ endpoints
        if payload.get("scope") == "sdk":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="SDK tokens cannot access this endpoint",
                headers={"WWW-Authenticate": "Bearer"},
            )

        developer_id: str = payload.get("sub")
        if developer_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    developer = developer_repository.get(db, UUID(developer_id))
    if not developer:
        raise credentials_exception

    return developer


def get_current_developer_optional(
    db: DbSession,
    token: Annotated[str | None, Depends(oauth2_scheme)] = None,
) -> Developer | None:
    """Get current authenticated developer from JWT token, or None if not authenticated.

    SDK-scoped tokens return None - they are not developer tokens.

    Sync on purpose — see :func:`get_current_developer`.
    """
    if not token:
        return None

    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])

        # SDK tokens are not developer tokens - return None to allow fallback to API key
        if payload.get("scope") == "sdk":
            return None

        developer_id: str = payload.get("sub")
        if developer_id is None:
            return None

        # Validate that developer_id is a valid UUID
        try:
            developer_uuid = UUID(developer_id)
        except ValueError:
            return None

    except JWTError:
        return None

    return developer_repository.get(db, developer_uuid)


DeveloperDep = Annotated[Developer, Depends(get_current_developer)]
DeveloperOptionalDep = Annotated[Developer | None, Depends(get_current_developer_optional)]


def get_sdk_auth(
    db: DbSession,
    token: Annotated[str | None, Depends(oauth2_scheme)] = None,
    x_open_wearables_api_key: str | None = Header(None, alias="X-Open-Wearables-API-Key"),
) -> SDKAuthContext:
    """Authenticate SDK requests using either SDK user token or API key.

    Accepts:
    - SDK token (Bearer token with scope="sdk")
    - API key (X-Open-Wearables-API-Key header)

    Returns SDKAuthContext with auth_type and relevant identifiers.

    Sync on purpose — see :func:`get_current_developer`.
    """
    # Try SDK user token first
    if token:
        try:
            payload = jwt.decode(
                token,
                settings.secret_key,
                algorithms=[settings.algorithm],
            )
            if payload.get("scope") == "sdk":
                sub = payload.get("sub")
                return SDKAuthContext(
                    auth_type="sdk_token",
                    user_id=sub,
                    app_id=payload.get("app_id"),
                )
        except JWTError:
            pass  # Fall through to API key check

    # Fall back to API key (backwards compatibility)
    if x_open_wearables_api_key:
        api_key = validate_api_key(db, x_open_wearables_api_key)
        return SDKAuthContext(auth_type="api_key", api_key_id=str(api_key.id))

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required: provide SDK token or API key",
    )


SDKAuthDep = Annotated[SDKAuthContext, Depends(get_sdk_auth)]


def get_combined_auth(
    db: DbSession,
    token: Annotated[str | None, Depends(oauth2_scheme)] = None,
    x_open_wearables_api_key: str | None = Header(None, alias="X-Open-Wearables-API-Key"),
) -> SDKAuthContext:
    """Accept a developer JWT, an API key, or an SDK user token.

    For endpoints both the dashboard and the mobile SDK call.
    ``get_current_developer_optional`` returns None for SDK-scoped tokens, so they fall
    through to ``get_sdk_auth``. An ``sdk_token`` caller speaks only for its own user, so
    endpoints branching on ``auth_type`` have to scope it themselves.

    Sync on purpose — see :func:`get_current_developer`.
    """
    if developer := get_current_developer_optional(db, token):
        return SDKAuthContext(auth_type="developer", developer_id=str(developer.id))

    return get_sdk_auth(db, token, x_open_wearables_api_key)


CombinedAuthDep = Annotated[SDKAuthContext, Depends(get_combined_auth)]
