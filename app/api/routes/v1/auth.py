from fastapi import APIRouter

from app.services import user_service, api_key_backend
from app.schemas import UserRead, UserCreate, UserUpdate

router = APIRouter()


router.include_router(
    user_service.get_auth_router(api_key_backend),
    prefix="/auth",  # /login  /logout
)
router.include_router(
    user_service.get_register_router(UserRead, UserCreate),
    prefix="/auth",  # /register
)
router.include_router(
    user_service.get_reset_password_router(),
    prefix="/auth",  # /forgot-password. /reset-password
)
router.include_router(
    user_service.get_users_router(UserRead, UserUpdate),
    prefix="/users",  # /me  /{user_id}
)
