from typing import Annotated
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.config import settings
from app.database import DbSession
from app.schemas.model_crud.credentials import ConnectTokenResponse
from app.schemas.model_crud.user_management import (
    UserCreate,
    UserDetailRead,
    UserInclude,
    UserQueryParams,
    UserRead,
    UserUpdate,
)
from app.schemas.utils import OldPaginatedResponse
from app.services import ApiKeyDep, user_service
from app.utils.connect_token import create_connect_token
from app.utils.problem import problem_doc

router = APIRouter()


@router.get(
    "/users",
    response_model=OldPaginatedResponse[UserRead],
    # Keeps opt-in expansions out of the payload entirely rather than serializing them as null.
    response_model_exclude_unset=True,
)
def list_users(
    db: DbSession,
    _api_key: ApiKeyDep,
    query_params: Annotated[UserQueryParams, Query()],
):
    """List users with pagination, sorting, and search."""
    return user_service.get_users_paginated(db, query_params)


@router.get(
    "/users/{user_id}",
    response_model=UserDetailRead,
    # Same as the list: an expansion that was not asked for stays out of the payload.
    response_model_exclude_unset=True,
    responses={
        **problem_doc(401, "Authentication required", "Authentication required: provide JWT token or API key"),
        **problem_doc(404, "User not found", "User with ID: 123e4567-e89b-12d3-a456-426614174000 not found."),
    },
)
def get_user(
    user_id: UUID,
    db: DbSession,
    _api_key: ApiKeyDep,
    include: Annotated[
        list[UserInclude],
        Query(
            default_factory=list,
            description="Optional expansions to embed; repeat the parameter for several",
        ),
    ],
):
    """Returns one user with its latest sync state and connection summary."""
    return user_service.get_detail(db, user_id, include)


@router.post("/users", status_code=status.HTTP_201_CREATED, response_model=UserRead)
def create_user(payload: UserCreate, db: DbSession, _api_key: ApiKeyDep):
    return user_service.create(db, payload)


@router.delete("/users/{user_id}", response_model=UserRead)
def delete_user(user_id: UUID, db: DbSession, _api_key: ApiKeyDep):
    return user_service.delete(db, user_id, raise_404=True)


@router.patch("/users/{user_id}", response_model=UserRead)
def update_user(user_id: UUID, payload: UserUpdate, db: DbSession, _api_key: ApiKeyDep):
    return user_service.update(db, user_id, payload, raise_404=True)


@router.post("/users/{user_id}/connect-token", response_model=ConnectTokenResponse)
def mint_connect_token(user_id: UUID, db: DbSession, _api_key: ApiKeyDep):
    """Mint a token that lets an end user connect providers for this user only.

    Send it to `/oauth/{provider}/authorize` as `X-Open-Wearables-Connect-Token`, or share `pair_url`.
    """
    user_service.get(db, user_id, raise_404=True)
    token, expires_at = create_connect_token(user_id)
    pair_url = f"{settings.frontend_url.rstrip('/')}/users/{user_id}/pair?{urlencode({'t': token})}"
    return ConnectTokenResponse(token=token, expires_at=expires_at, pair_url=pair_url)
