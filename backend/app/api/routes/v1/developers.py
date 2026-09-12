from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.database import DbSession
from app.schemas.model_crud.user_management import DeveloperRead, DeveloperUpdate
from app.services import DeveloperDep, developer_service

router = APIRouter()


@router.get("", response_model=list[DeveloperRead])
def list_developers(db: DbSession, _auth: DeveloperDep):
    """List all developers (team members)."""
    return db.query(developer_service.crud.model).all()


@router.get("/{developer_id}", response_model=DeveloperRead)
def get_developer(developer_id: UUID, db: DbSession, _auth: DeveloperDep):
    """Get developer by ID."""
    return developer_service.get(db, developer_id, raise_404=True)


@router.patch(
    "/{developer_id}",
    response_model=DeveloperRead,
    responses={
        403: {
            "description": "The ID is not the authenticated developer's own",
            "content": {"application/json": {"example": {"detail": "You can only update your own developer account"}}},
        },
    },
)
def update_developer(
    developer_id: UUID,
    payload: DeveloperUpdate,
    db: DbSession,
    developer: DeveloperDep,
):
    """Update the authenticated developer's own profile.

    Developers have no roles, so there is no one entitled to edit another developer's
    email or password.
    """
    if developer_id != developer.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own developer account",
        )
    return developer_service.update_developer_info(db, developer_id, payload, raise_404=True)


@router.delete("/{developer_id}", response_model=DeveloperRead)
def delete_developer(developer_id: UUID, db: DbSession, _auth: DeveloperDep):
    """Delete developer by ID."""
    return developer_service.delete(db, developer_id, raise_404=True)
