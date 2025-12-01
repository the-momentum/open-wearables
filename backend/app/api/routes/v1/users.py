from uuid import UUID

from fastapi import APIRouter, status

from app.database import DbSession
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services import ApiKeyDep, DeveloperDep, user_service

router = APIRouter()


@router.get("/users", response_model=list[UserRead])
async def list_users(db: DbSession, _developer: DeveloperDep) -> list[UserRead]:
    return db.query(user_service.crud.model).all()


@router.get("/users/{user_id}", response_model=UserRead)
async def get_user(user_id: UUID, db: DbSession, _api_key: ApiKeyDep) -> UserRead:
    return user_service.get(db, user_id, raise_404=True)


@router.post("/users", status_code=status.HTTP_201_CREATED, response_model=UserRead)
async def create_user(payload: UserCreate, db: DbSession, _api_key: ApiKeyDep) -> UserRead:
    return user_service.create(db, payload)


@router.delete("/users/{user_id}", response_model=UserRead)
async def delete_user(user_id: UUID, db: DbSession, _developer: DeveloperDep) -> UserRead:
    return user_service.delete(db, user_id, raise_404=True)


@router.patch("/users/{user_id}", response_model=UserRead)
async def update_user(user_id: UUID, payload: UserUpdate, db: DbSession, _developer: DeveloperDep) -> UserRead:
    return user_service.update(db, user_id, payload, raise_404=True)
