from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.config import settings

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

_TokenDep = Annotated[str | None, Depends(_oauth2_scheme)]

_AUTH_HEADERS = {"WWW-Authenticate": "Bearer"}


def _unauthorized(detail: str = "Could not validate credentials") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail, headers=_AUTH_HEADERS)


class JWTAuth:
    def __init__(self) -> None:
        self._secret_key = settings.secret_key
        self._algorithm = settings.algorithm

    def _decode(self, token: str | None) -> dict:
        if not token:
            raise _unauthorized()
        try:
            return jwt.decode(token, self._secret_key, algorithms=[self._algorithm])
        except jwt.ExpiredSignatureError:
            raise _unauthorized("Token has expired")
        except jwt.PyJWTError:
            raise _unauthorized()

    async def validate_token(self, token: _TokenDep) -> None:
        self._decode(token)

    async def get_user_id(self, token: _TokenDep) -> UUID:
        payload = self._decode(token)
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise _unauthorized()
        try:
            return UUID(user_id)
        except ValueError:
            raise _unauthorized()


jwt_auth = JWTAuth()

ValidToken = Annotated[None, Depends(jwt_auth.validate_token)]
CurrentUserId = Annotated[UUID, Depends(jwt_auth.get_user_id)]
