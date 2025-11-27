from fastapi import APIRouter

from app.schemas import DeveloperCreate, DeveloperRead, DeveloperUpdate
from app.services import developer_auth_backend, developer_service

router = APIRouter()

# /login /logout
router.include_router(developer_service.get_auth_router(developer_auth_backend))

# /register
router.include_router(developer_service.get_register_router(DeveloperRead, DeveloperCreate))

# /forgot-password /reset-password
router.include_router(developer_service.get_reset_password_router())

# /me /{developer_id}
router.include_router(developer_service.get_users_router(DeveloperRead, DeveloperUpdate))
