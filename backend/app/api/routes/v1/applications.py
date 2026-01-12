from fastapi import APIRouter, status

from app.database import DbSession
from app.schemas.application import (
    ApplicationCreate,
    ApplicationRead,
    ApplicationReadWithSecret,
)
from app.services import DeveloperDep, application_service

router = APIRouter()


@router.get("/applications")
async def list_applications(db: DbSession, developer: DeveloperDep) -> list[ApplicationRead]:
    """List all applications for current developer."""
    applications = application_service.list_applications(db, developer.id)
    return [
        ApplicationRead(
            id=app.id,
            app_id=app.app_id,
            name=app.name,
            created_at=app.created_at,
        )
        for app in applications
    ]


@router.post(
    "/applications",
    status_code=status.HTTP_201_CREATED,
)
async def create_application(
    payload: ApplicationCreate,
    db: DbSession,
    developer: DeveloperDep,
) -> ApplicationReadWithSecret:
    """Create new application.

    Returns app_secret only once - store it securely as it cannot be retrieved again.
    """
    application, plain_secret = application_service.create_application(db, developer.id, payload.name)
    return ApplicationReadWithSecret(
        id=application.id,
        app_id=application.app_id,
        name=application.name,
        created_at=application.created_at,
        app_secret=plain_secret,
    )


@router.delete("/applications/{app_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application(
    app_id: str,
    db: DbSession,
    developer: DeveloperDep,
) -> None:
    """Delete application."""
    application_service.delete_application(db, app_id, developer.id)


@router.post(
    "/applications/{app_id}/rotate-secret",
)
async def rotate_application_secret(
    app_id: str,
    db: DbSession,
    developer: DeveloperDep,
) -> ApplicationReadWithSecret:
    """Rotate application secret.

    Returns new secret only once - store it securely as it cannot be retrieved again.
    The old secret will no longer work after rotation.
    """
    application, new_secret = application_service.rotate_secret(db, app_id, developer.id)
    return ApplicationReadWithSecret(
        id=application.id,
        app_id=application.app_id,
        name=application.name,
        created_at=application.created_at,
        app_secret=new_secret,
    )
