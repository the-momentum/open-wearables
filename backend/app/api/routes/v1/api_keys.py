from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, status

from app.database import DbSession
from app.models import ApiKey
from app.schemas.model_crud.credentials import ApiKeyRead, ApiKeyReadWithSecret, ApiKeyUpdate
from app.services import DeveloperDep, api_key_service

router = APIRouter()


def _with_secret(api_key: ApiKey, raw_key: str) -> ApiKeyReadWithSecret:
    return ApiKeyReadWithSecret(
        id=api_key.id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        created_by=api_key.created_by,
        created_at=api_key.created_at,
        key=raw_key,
    )


@router.get("/api-keys", response_model=list[ApiKeyRead])
def list_api_keys(db: DbSession, _developer: DeveloperDep):
    """List all API keys.

    Only a short prefix of each key is returned - the full value is never stored.
    """
    return api_key_service.list_api_keys(db)


@router.post("/api-keys", status_code=status.HTTP_201_CREATED)
def create_api_key(
    db: DbSession,
    _developer: DeveloperDep,
    name: Annotated[str, Body(embed=True, description="Name for the API key")] = "Default",
) -> ApiKeyReadWithSecret:
    """Generate new API key.

    Returns the full key only once - store it securely as it cannot be retrieved again.
    """
    return _with_secret(*api_key_service.create_api_key(db, _developer.id, name))


@router.delete("/api-keys/{key_id}", response_model=ApiKeyRead)
def delete_api_key(key_id: UUID, db: DbSession, _developer: DeveloperDep):
    """Delete API key by id."""
    return api_key_service.delete(db, key_id, raise_404=True)


@router.patch("/api-keys/{key_id}", response_model=ApiKeyRead)
def update_api_key(
    key_id: UUID,
    payload: ApiKeyUpdate,
    db: DbSession,
    _developer: DeveloperDep,
):
    """Update API key (future: name, scopes)."""
    return api_key_service.update(db, key_id, payload, raise_404=True)


@router.post("/api-keys/{key_id}/rotate", status_code=status.HTTP_201_CREATED)
def rotate_api_key(key_id: UUID, db: DbSession, _developer: DeveloperDep) -> ApiKeyReadWithSecret:
    """Rotate API key - delete old and generate new one with the same name.

    Returns the full key only once - store it securely as it cannot be retrieved again.
    """
    return _with_secret(*api_key_service.rotate_api_key(db, key_id, _developer.id))
