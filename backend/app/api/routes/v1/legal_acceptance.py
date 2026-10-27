"""Users accepting the instance's legal documents: reported by the Open Wearables Connect app,
listed for the dashboard."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from app.database import DbSession
from app.schemas.model_crud.legal_acceptance import LegalAcceptanceCreate, LegalAcceptanceRead
from app.services import DeveloperDep
from app.services.legal_acceptance_service import legal_acceptance_service
from app.utils.auth import SDKAuthDep

router = APIRouter()
sdk_router = APIRouter()


@sdk_router.post("/sdk/users/{user_id}/legal-acceptance", status_code=status.HTTP_201_CREATED)
def accept_legal_documents(
    user_id: UUID,
    payload: LegalAcceptanceCreate,
    db: DbSession,
    auth: SDKAuthDep,
    response: Response,
) -> LegalAcceptanceRead:
    """The user accepted the instance's privacy policy and terms (`instance/info`) in the app.

    Requires the user's own SDK token: the acceptance is theirs, an API key cannot give it.
    201 for a new acceptance, 200 when this version was already accepted. 409 when
    `documents_version` is not the current version: read `instance/info` again and ask the
    user about the current documents. 400 when `accepted_at` is in the future.
    """
    if auth.auth_type != "sdk_token" or auth.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token does not belong to this user")
    acceptance, created = legal_acceptance_service.record(db, user_id, payload)
    if not created:
        response.status_code = status.HTTP_200_OK
    return acceptance


@router.get("/users/{user_id}/legal-acceptances")
def list_legal_acceptances(user_id: UUID, db: DbSession, _developer: DeveloperDep) -> list[LegalAcceptanceRead]:
    """Versions of the instance's legal documents the user accepted, newest first."""
    return legal_acceptance_service.list_for_user(db, user_id)
