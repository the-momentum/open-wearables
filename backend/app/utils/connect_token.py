from datetime import datetime, timedelta, timezone
from uuid import UUID

from jose import JWTError, jwt

from app.config import settings
from app.utils.config_utils import derive_secret

CONNECT_SCOPE = "connect"


def _key() -> str:
    """Its own key, so no other token decoder accepts a connect token, nor this one theirs."""
    return derive_secret(settings.secret_key, "connect-token")


def create_connect_token(user_id: UUID) -> tuple[str, datetime]:
    """Token that lets its holder start a provider OAuth flow for one user, and nothing else."""
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.connect_token_expire_days)
    claims = {"sub": str(user_id), "scope": CONNECT_SCOPE, "exp": expires_at}
    return jwt.encode(claims, _key(), algorithm=settings.algorithm), expires_at


def decode_connect_token(token: str) -> UUID | None:
    """The user the token was issued for, or None if it is invalid, expired or not a connect token."""
    try:
        payload = jwt.decode(token, _key(), algorithms=[settings.algorithm])
        if payload.get("scope") != CONNECT_SCOPE:
            return None
        return UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        return None
