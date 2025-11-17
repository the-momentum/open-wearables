from logging import getLogger
from typing import Annotated, AsyncGenerator
from uuid import UUID

from fastapi import Depends
from fastapi_users import BaseUserManager, FastAPIUsers
from fastapi_users.authentication import AuthenticationBackend, BearerTransport, JWTStrategy
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase

from app.config import settings
from app.database import AsyncDbSession
from app.models import Developer
from app.services.services import CustomBaseManager


class DeveloperManager(CustomBaseManager[Developer], BaseUserManager[Developer, UUID]):
    def __init__(self, user_db: SQLAlchemyUserDatabase):
        super().__init__(user_db, model=Developer, log=getLogger("developer_manager"))


async def get_developer_db(session: AsyncDbSession) -> AsyncGenerator[SQLAlchemyUserDatabase, None]:
    yield SQLAlchemyUserDatabase(session, Developer)


async def get_developer_manager(
    developer_db: SQLAlchemyUserDatabase = Depends(get_developer_db),
) -> AsyncGenerator[DeveloperManager, None]:
    yield DeveloperManager(developer_db)


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=settings.secret_key, lifetime_seconds=settings.token_lifetime)


bearer_transport = BearerTransport(tokenUrl="/api/v1/auth/login")

developer_auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

developer_service = FastAPIUsers[Developer, UUID](
    get_developer_manager,
    [developer_auth_backend],
)

current_active_user = developer_service.current_user(active=True)
current_active_user_optional = developer_service.current_user(active=True, optional=True)

DeveloperDep = Annotated[Developer, Depends(current_active_user)]
