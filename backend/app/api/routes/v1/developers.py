from uuid import UUID

from fastapi import APIRouter

from app.database import DbSession
from app.schemas import DeveloperRead, DeveloperUpdate
from app.services import DeveloperDep, developer_service

router = APIRouter()


@router.get("/", response_model=list[DeveloperRead])
async def list_developers(db: DbSession, _auth: DeveloperDep):
    """List all developers (team members)."""
    return db.query(developer_service.crud.model).all()


@router.get("/{developer_id}", response_model=DeveloperRead)
async def get_developer(developer_id: UUID, db: DbSession, _auth: DeveloperDep):
    """Get developer by ID."""
    return developer_service.get(db, developer_id, raise_404=True)


@router.patch("/{developer_id}", response_model=DeveloperRead)
async def update_developer(
    developer_id: UUID,
    payload: DeveloperUpdate,
    db: DbSession,
    _auth: DeveloperDep,
):
    """Update developer by ID."""
    return developer_service.update_developer_info(db, developer_id, payload, raise_404=True)


@router.delete("/{developer_id}", response_model=DeveloperRead)
async def delete_developer(developer_id: UUID, db: DbSession, _auth: DeveloperDep):
    """Delete developer by ID."""
    return developer_service.delete(db, developer_id, raise_404=True)
