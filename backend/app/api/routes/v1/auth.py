from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.database import DbSession
from app.schemas import DeveloperRead, DeveloperUpdate
from app.schemas.developer import DeveloperCreate
from app.schemas.oauth import Token
from app.services import DeveloperDep, developer_service
from app.utils.security import create_access_token, verify_password

router = APIRouter()


@router.post("/login", response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession,
):
    """Authenticate developer and return access token."""
    # Find developer by username
    developers = developer_service.crud.get_all(
        db,
        filters={"username": form_data.username},
        offset=0,
        limit=1,
        sort_by=None,
    )
    if not developers:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    developer = developers[0]
    if not verify_password(form_data.password, developer.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(subject=str(developer.id))
    return Token(access_token=access_token, token_type="bearer")


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=DeveloperRead)
async def register(
    developer_in: DeveloperCreate,
    db: DbSession,
):
    """Register a new developer."""
    return developer_service.create(db, developer_in)


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
    return developer_service.update(db, developer.id, payload, raise_404=True)


@router.get("/{developer_id}", response_model=DeveloperRead)
async def get_developer(developer_id: UUID, db: DbSession, _auth: DeveloperDep):
    """Get developer by ID (admin only)."""
    return developer_service.get(db, developer_id, raise_404=True)


@router.patch("/{developer_id}", response_model=DeveloperRead)
async def update_developer(
    developer_id: UUID,
    payload: DeveloperUpdate,
    db: DbSession,
    _auth: DeveloperDep,
):
    """Update developer by ID (admin only)."""
    return developer_service.update(db, developer_id, payload, raise_404=True)


@router.delete("/{developer_id}", response_model=DeveloperRead)
async def delete_developer(developer_id: UUID, db: DbSession, _auth: DeveloperDep):
    """Delete developer by ID (admin only)."""
    return developer_service.delete(db, developer_id, raise_404=True)
