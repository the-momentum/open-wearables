from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.database import DbSession
from app.schemas.common import PaginatedResponse
from app.schemas.user import UserCreate, UserQueryParams, UserRead, UserUpdate
from app.services import ApiKeyDep, DeveloperDep, user_service

router = APIRouter()


@router.get("/users", response_model=PaginatedResponse[UserRead])
async def list_users(
    db: DbSession,
    _api_key: ApiKeyDep,
    query_params: Annotated[UserQueryParams, Depends()],
):
    """List users with pagination, sorting, and search."""
    return user_service.get_users_paginated(db, query_params)


@router.get("/users/{user_id}", response_model=UserRead)
async def get_user(user_id: UUID, db: DbSession, _api_key: ApiKeyDep):
    return user_service.get(db, user_id, raise_404=True)


@router.post("/users", status_code=status.HTTP_201_CREATED, response_model=UserRead)
async def create_user(payload: UserCreate, db: DbSession, _api_key: ApiKeyDep):
    return user_service.create(db, payload)


@router.delete("/users/{user_id}", response_model=UserRead)
async def delete_user(user_id: UUID, db: DbSession, _developer: DeveloperDep):
    return user_service.delete(db, user_id, raise_404=True)


@router.patch("/users/{user_id}", response_model=UserRead)
async def update_user(user_id: UUID, payload: UserUpdate, db: DbSession, _developer: DeveloperDep):
    return user_service.update(db, user_id, payload, raise_404=True)
