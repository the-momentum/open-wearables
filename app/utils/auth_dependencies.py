from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.services import auth0_service
from app.database import DbSession
from app.services import user_service
from app.schemas import UserInfo

security = HTTPBearer()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: DbSession
) -> UserInfo:
    token = credentials.credentials
    payload = await auth0_service.verify_token(token)
    
    auth0_id = auth0_service.get_user_id(payload)
    # email = auth0_service.get_user_email(token)
    permissions = auth0_service.get_user_permissions(payload)
    
    user = user_service.get_or_create_user(
        db,
        auth0_id=auth0_id,
        email="email@test.com"
    )
    
    return UserInfo(
        user_id=user.id,
        auth0_id=auth0_id,
        email=str(user.email),
        permissions=permissions,
        payload=payload
    )


async def get_current_user_id(
    current_user: Annotated[UserInfo, Depends(get_current_user)]
) -> str:
    return str(current_user.user_id)
