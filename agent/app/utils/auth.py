from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from app.config import settings

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

_TokenDep = Annotated[str | None, Depends(_oauth2_scheme)]


class JWTAuth:
    def __init__(self) -> None:
        self._secret_key = settings.secret_key
        self._algorithm = settings.algorithm

    def _decode(self, token: str | None) -> dict:
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            payload = jwt.decode(token, self._secret_key, algorithms=[self._algorithm])
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        exp = payload.get("exp")
        if exp is None or datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(tz=timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return payload

    async def validate_token(self, token: _TokenDep) -> None:
        self._decode(token)

    async def get_user_id(self, token: _TokenDep) -> UUID:
        payload = self._decode(token)
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return UUID(user_id)


jwt_auth = JWTAuth()

ValidToken = Annotated[None, Depends(jwt_auth.validate_token)]
CurrentUserId = Annotated[UUID, Depends(jwt_auth.get_user_id)]
