from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.database import DbSession
from app.schemas.common import PaginatedResponse
from app.schemas.series_types import get_series_type_from_id
from app.schemas.system_info import EventTypeMetric, SeriesTypeMetric, UserDataStats
from app.schemas.user import UserCreate, UserQueryParams, UserRead, UserUpdate
from app.services import ApiKeyDep, DeveloperDep, user_service
from app.services.event_record_service import event_record_service
from app.services.timeseries_service import timeseries_service

router = APIRouter()


@router.get("/users", response_model=PaginatedResponse[UserRead])
async def list_users(
    db: DbSession,
    _api_key: ApiKeyDep,
    query_params: Annotated[UserQueryParams, Depends()],
):
    """List users with pagination, sorting, and search."""
    return user_service.get_users_paginated(db, query_params)


@router.get(
    "/users/{user_id}",
    response_model=UserRead,
    responses={
        401: {
            "description": "Authentication required",
            "content": {
                "application/json": {"example": {"detail": "Authentication required: provide JWT token or API key"}}
            },
        },
        404: {
            "description": "User not found",
            "content": {
                "application/json": {
                    "example": {"detail": "User with ID: 123e4567-e89b-12d3-a456-426614174000 not found."}
                }
            },
        },
        400: {
            "description": "Validation error",
            "content": {"application/json": {"example": {"detail": "Input should be a valid UUID"}}},
        },
    },
)
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


@router.get("/users/{user_id}/stats", response_model=UserDataStats)
async def get_user_stats(user_id: UUID, db: DbSession, _api_key: ApiKeyDep):
    """Get data type counts and totals for a specific user."""
    user_service.get(db, user_id, raise_404=True)

    series_type_counts = timeseries_service.get_count_by_series_type_for_user(db, user_id)
    event_type_counts = event_record_service.get_count_by_category_and_type_for_user(db, user_id)

    total_data_points = sum(count for _, count in series_type_counts)

    series_types = []
    for type_id, count in series_type_counts:
        try:
            series_type = get_series_type_from_id(type_id)
            series_types.append(SeriesTypeMetric(series_type=series_type.value, count=count))
        except KeyError:
            pass

    event_types = [
        EventTypeMetric(category=category, type=event_type, count=count)
        for category, event_type, count in event_type_counts
    ]

    return UserDataStats(
        total_data_points=total_data_points,
        series_types=series_types,
        event_types=event_types,
    )
