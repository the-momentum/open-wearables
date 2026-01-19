from datetime import datetime, timedelta, timezone

from jose import jwt

from app.config import settings


def create_sdk_user_token(app_id: str, user_id: str, infinite: bool = False) -> str:
    """Create JWT with SDK scope for a specific user.

    The token is scoped to SDK endpoints only and contains:
    - sub: The user_id (UUID string)
    - scope: "sdk" to identify this as an SDK token
    - app_id: The application ID that created this token
    - exp: Expiration timestamp (60 minutes from now, or omitted if infinite=True)

    Args:
        app_id: The application ID that requested this token
        user_id: The OpenWearables User ID (UUID string)
        infinite: If True, token will not expire (no exp claim)

    Returns:
        JWT token string
    """
    claims = {
        "sub": user_id,
        "scope": "sdk",
        "app_id": app_id,
    }

    if not infinite:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
        claims["exp"] = expire

    return jwt.encode(claims, settings.secret_key, algorithm=settings.algorithm)
