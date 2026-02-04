from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.database import DbSession
from app.schemas import DeveloperRead, DeveloperUpdate
from app.schemas.token import TokenResponse
from app.services import DeveloperDep, developer_service, refresh_token_service
from app.utils.security import create_access_token, verify_password

router = APIRouter()


@router.post("/login")
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession,
) -> TokenResponse:
    """Authenticate developer and return access token with refresh token."""
    # Find developer by email
    developers = developer_service.crud.get_all(
        db,
        filters={"email": form_data.username},  # OAuth2PasswordRequestForm uses 'username' field for login
        offset=0,
        limit=1,
        sort_by=None,
    )
    if not developers:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    developer = developers[0]
    if not verify_password(form_data.password, developer.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(subject=str(developer.id))
    refresh_token = refresh_token_service.create_developer_refresh_token(db, developer.id)

    return TokenResponse(access_token=access_token, token_type="bearer", refresh_token=refresh_token)


@router.post("/logout")
async def logout(_developer: DeveloperDep):
    """Logout developer (token invalidation should be handled client-side)."""
    return {"message": "Successfully logged out"}


# TODO: Implement /forgot-password and /reset-password


@router.get("/me", response_model=DeveloperRead)
async def get_current_developer_info(db: DbSession, developer: DeveloperDep):
    """Get current authenticated developer."""
    return developer


@router.patch("/me", response_model=DeveloperRead)
async def update_current_developer(
    payload: DeveloperUpdate,
    db: DbSession,
    developer: DeveloperDep,
):
    """Update current authenticated developer."""
    return developer_service.update_developer_info(db, developer.id, payload)
