from logging import getLogger
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.config import DEFAULT_ADMIN_PASSWORD, settings
from app.database import DbSession
from app.schemas.auth import PasswordChangePrompt, TokenResponse
from app.schemas.model_crud.user_management import DeveloperRead, DeveloperUpdate, PasswordChange
from app.services import DeveloperDep, developer_service, refresh_token_service
from app.utils.config_utils import EnvironmentType
from app.utils.security import create_access_token, verify_password

router = APIRouter()
logger = getLogger(__name__)


def _password_change_prompt(password: str) -> PasswordChangePrompt | None:
    """The seeded default is public, so an account still using it must be told to change it."""
    if password != DEFAULT_ADMIN_PASSWORD:
        return None
    if settings.environment == EnvironmentType.PRODUCTION:
        return PasswordChangePrompt.REQUIRED
    return PasswordChangePrompt.RECOMMENDED


@router.post("/login")
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession,
) -> TokenResponse:
    """Authenticate developer and return access token with refresh token."""
    # The default is public, so in production it must never yield a session - not even one
    # that only allows a password change, since whoever logs in first could set their own.
    # Checked before the account lookup so the response does not reveal who still uses it.
    if settings.environment == EnvironmentType.PRODUCTION and form_data.password == DEFAULT_ADMIN_PASSWORD:
        logger.warning("Rejected a production login with the default admin password; set ADMIN_PASSWORD to rotate it.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "The default admin password is disabled in production. "
                "Set ADMIN_PASSWORD on the backend and restart it to replace the password."
            ),
        )

    developer = developer_service.get_by_email(db, form_data.username)
    if not developer:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(form_data.password, developer.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(subject=str(developer.id))
    refresh_token = refresh_token_service.create_developer_refresh_token(db, developer.id)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        refresh_token=refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
        password_change=_password_change_prompt(form_data.password),
    )


@router.post("/logout")
def logout(_developer: DeveloperDep):
    """Logout developer (token invalidation should be handled client-side)."""
    return {"message": "Successfully logged out"}


@router.post("/change-password")
def change_password(
    payload: PasswordChange,
    db: DbSession,
    developer: DeveloperDep,
):
    """Change password for the current authenticated developer."""
    # Verify the current password
    if not verify_password(payload.current_password, developer.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password",
        )

    # Update using existing developer_service logic
    developer_service.update_developer_info(
        db, developer.id, DeveloperUpdate(password=payload.new_password), raise_404=True
    )

    return {"message": "Password updated successfully"}


@router.get("/me", response_model=DeveloperRead)
def get_current_developer_info(db: DbSession, developer: DeveloperDep):
    """Get current authenticated developer."""
    return developer


@router.patch("/me", response_model=DeveloperRead)
def update_current_developer(
    payload: DeveloperUpdate,
    db: DbSession,
    developer: DeveloperDep,
):
    """Update current authenticated developer."""
    return developer_service.update_developer_info(db, developer.id, payload)
