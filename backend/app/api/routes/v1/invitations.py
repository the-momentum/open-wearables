from uuid import UUID

from fastapi import APIRouter, status

from app.database import DbSession
from app.schemas import DeveloperRead
from app.schemas.invitation import InvitationAccept, InvitationCreate, InvitationRead
from app.services import DeveloperDep
from app.services.invitation_service import invitation_service

router = APIRouter()


# ============ Invitation Management (Authenticated) ============


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=InvitationRead)
async def create_invitation(
    payload: InvitationCreate,
    db: DbSession,
    developer: DeveloperDep,
):
    """Create and send a new invitation."""
    return invitation_service.create_invitation(db, payload, developer)


@router.get("/", response_model=list[InvitationRead])
async def list_invitations(db: DbSession, _auth: DeveloperDep):
    """List all pending invitations."""
    return invitation_service.get_pending_invitations(db)


@router.delete("/{invitation_id}", response_model=InvitationRead)
async def revoke_invitation(invitation_id: UUID, db: DbSession, _auth: DeveloperDep):
    """Revoke a pending invitation."""
    return invitation_service.revoke_invitation(db, invitation_id)


@router.post("/{invitation_id}/resend", response_model=InvitationRead)
async def resend_invitation(invitation_id: UUID, db: DbSession, _auth: DeveloperDep):
    """Resend an invitation email."""
    return invitation_service.resend_invitation(db, invitation_id)


# ============ Accept Invitation (Public) ============


@router.post("/accept", status_code=status.HTTP_201_CREATED, response_model=DeveloperRead)
async def accept_invitation(payload: InvitationAccept, db: DbSession):
    """Accept an invitation and create a developer account (public endpoint)."""
    return invitation_service.accept_invitation(
        db,
        payload.token,
        payload.first_name,
        payload.last_name,
        payload.password,
    )
