from datetime import datetime, timedelta, timezone

from jose import jwt

from app.config import settings


def create_sdk_user_token(app_id: str, user_id: str) -> str:
    """Create JWT with SDK scope for a specific user.

    The token is scoped to SDK endpoints only and contains:
    - sub: The user_id (UUID string)
    - scope: "sdk" to identify this as an SDK token
    - app_id: The application ID that created this token
    - exp: Expiration timestamp (configured via access_token_expire_minutes)

    Args:
        app_id: The application ID that requested this token
        user_id: The OpenWearables User ID (UUID string)

    Returns:
        JWT token string
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    claims = {
        "sub": user_id,
        "scope": "sdk",
        "app_id": app_id,
        "exp": expire,
    }

    return jwt.encode(claims, settings.secret_key, algorithm=settings.algorithm)
