from uuid import UUID
from logging import getLogger
from typing import AsyncGenerator, Any

from fastapi import Depends, Request, Response
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin
from fastapi_users.authentication import AuthenticationBackend, BearerTransport, JWTStrategy
from fastapi_users.db import SQLAlchemyUserDatabase

from app.config import settings
from app.database import AsyncDbSession
from app.models import User


type OptRequest = Request | None


class UserManager(UUIDIDMixin, BaseUserManager[User, UUID]):
    reset_password_token_secret = settings.secret_key
    verification_token_secret = settings.secret_key

    def __init__(self, **kwargs):
        self.logger = getLogger("user_manager")
        super().__init__(**kwargs)

    async def on_after_register(self, user: User, request: OptRequest = None) -> None:
        self.logger.debug(f"User {user.id} has registered.")

    async def on_after_update(self, user: User, update_dict: dict[str, Any]) -> None:
        self.logger.debug(f"User {user.id} has been updated with {update_dict}.")

    async def on_after_login(
        self,
        user: User,
        request: OptRequest = None,
        response: Response | None = None,
    ) -> None:
        self.logger.debug(f"User {user.id} logged in.")

    async def on_after_request_verify(self, user: User, token: str, request: OptRequest = None) -> None:
        self.logger.debug(f"Verification requested for user {user.id}. Verification token: {token}.")

    async def on_after_verify(self, user: User, request: OptRequest = None) -> None:
        self.logger.debug(f"User {user.id} has been verified.")

    async def on_after_forgot_password(self, user: User, token: str, request: OptRequest = None) -> None:
        self.logger.debug(f"User {user.id} has forgot their password. Reset token: {token}.")

    async def on_after_reset_password(self, user: User, request: OptRequest = None) -> None:
        self.logger.debug(f"User {user.id} has reset their password.")

    async def on_before_delete(self, user: User, request: OptRequest = None) -> None:
        self.logger.debug(f"User {user.id} is going to be deleted.")

    async def on_after_delete(self, user: User, request: OptRequest = None) -> None:
        self.logger.debug(f"User {user.id} is successfully deleted.")


async def get_user_db(session: AsyncDbSession) -> AsyncGenerator[AsyncDbSession, None]:
    yield SQLAlchemyUserDatabase(session, User)


async def get_user_manager(
    user_db: SQLAlchemyUserDatabase = Depends(get_user_db),
) -> AsyncGenerator[UserManager, None]:
    yield UserManager(user_db)


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=settings.secret_key, lifetime_seconds=settings.token_lifetime)


def get_current_user_id() -> UUID:
    current_active_user = user_service.current_user(active=True)
    return str(current_active_user.id)


bearer_transport = BearerTransport(tokenUrl="/api/v1/auth/login")


api_key_backend = AuthenticationBackend(
    name="api-key",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

user_service = FastAPIUsers[User, UUID](
    get_user_manager,
    [api_key_backend],
)
