from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from app.config import settings
from app.database import DbSession
from app.models import Developer
from app.repositories.developer_repository import DeveloperRepository
from app.schemas.sdk import SDKAuthContext

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)
developer_repository = DeveloperRepository(Developer)


def _decode_and_validate_token(token: str) -> dict:
    """Decode JWT token and validate common claims.

    Common validation logic for both HTTP Bearer and Query param tokens.
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])

        # Reject SDK-scoped tokens - they can only access /sdk/ endpoints
        if payload.get("scope") == "sdk":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="SDK tokens cannot access this endpoint",
                headers={"WWW-Authenticate": "Bearer"},
            )

        developer_id: str = payload.get("sub")
        if not developer_id:
            # Common credential validation error for get_current_developer
            # This matches legacy behavior where missing 'sub' raises generic 401
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return payload
    except JWTError as exc:
        # Common credential validation error
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def get_current_developer(
    db: DbSession,
    token: Annotated[str | None, Depends(oauth2_scheme)],
) -> Developer:
    """Get current authenticated developer from JWT token.

    SDK-scoped tokens are rejected - they can only access /sdk/ endpoints.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        raise credentials_exception

    payload = _decode_and_validate_token(token)
    developer_id = payload.get("sub")

    developer = developer_repository.get(db, UUID(developer_id))
    if not developer:
        raise credentials_exception

    return developer


async def get_current_developer_optional(
    db: DbSession,
    token: Annotated[str | None, Depends(oauth2_scheme)] = None,
) -> Developer | None:
    """Get current authenticated developer from JWT token, or None if not authenticated.

    SDK-scoped tokens return None - they are not developer tokens.
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


async def get_sdk_auth(
    db: DbSession,
    token: Annotated[str | None, Depends(oauth2_scheme)] = None,
    x_open_wearables_api_key: str | None = Header(None, alias="X-Open-Wearables-API-Key"),
) -> SDKAuthContext:
    """Authenticate SDK requests using either SDK user token or API key.

    Accepts:
    - SDK token (Bearer token with scope="sdk")
    - API key (X-Open-Wearables-API-Key header)

    Returns SDKAuthContext with auth_type and relevant identifiers.
    """
    # Import here to avoid circular imports
    from app.services.api_key_service import api_key_service

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
                    user_id=UUID(sub) if sub else None,
                    app_id=payload.get("app_id"),
                )
        except JWTError:
            pass  # Fall through to API key check

    # Fall back to API key (backwards compatibility)
    if x_open_wearables_api_key:
        api_key = api_key_service.validate_api_key(db, x_open_wearables_api_key)
        return SDKAuthContext(auth_type="api_key", api_key_id=api_key.id)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required: provide SDK token or API key",
    )


SDKAuthDep = Annotated[SDKAuthContext, Depends(get_sdk_auth)]


def verify_query_token(
    token: Annotated[str | None, Query(description="JWT Bearer token for authentication")],
) -> str:
    """Validate a JWT token passed as a query parameter (for SSE/WebSocket).

    EventSource and native WebSocket APIs do not support custom HTTP headers,
    so the token is passed as ``?token=<jwt>`` instead of the usual Authorization header.

    Unlike ``get_current_developer``, this returns the subject ID directly
    without database lookup, for minimal overhead during high-frequency checks.

    Returns:
        The developer ID (``sub`` claim) from the token.

    Raises:
        HTTPException(401): If token is missing, invalid, expired, or has wrong scope.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: provide token query parameter",
        )

    # Use shared validation logic
    payload = _decode_and_validate_token(token)
    return payload["sub"]
