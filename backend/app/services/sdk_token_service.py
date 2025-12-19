from datetime import datetime, timedelta, timezone

from jose import jwt

from app.config import settings


def create_sdk_user_token(app_id: str, external_user_id: str) -> str:
    """Create JWT with SDK scope for a specific user.

    The token is scoped to SDK endpoints only and contains:
    - sub: The external_user_id provided by the mobile app
    - scope: "sdk" to identify this as an SDK token
    - app_id: The application ID that created this token
    - exp: Expiration timestamp (60 minutes from now)

    Args:
        app_id: The application ID that requested this token
        external_user_id: The user identifier from the mobile app's backend

    Returns:
        JWT token string
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)

    claims = {
        "sub": external_user_id,
        "scope": "sdk",
        "app_id": app_id,
        "exp": expire,
    }

    return jwt.encode(claims, settings.secret_key, algorithm=settings.algorithm)
