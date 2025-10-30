from typing import Annotated

from fastapi import APIRouter, Depends

from app.utils.auth_dependencies import get_current_user
from app.schemas import UserInfo, UserResponse

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: Annotated[UserInfo, Depends(get_current_user)]
) -> UserResponse:
    return UserResponse(
        user_id=current_user.user_id,
        auth0_id=current_user.auth0_id,
        email=current_user.email,
        permissions=current_user.permissions
    )
