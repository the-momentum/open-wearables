from uuid import UUID

from fastapi import APIRouter, Response, status

from app.database import DbSession
from app.schemas.model_crud.activities import PersonalRecordResponse, PersonalRecordUpsert
from app.services import ApiKeyDep, personal_record_service

router = APIRouter()


@router.get("/users/{user_id}/personal-record", response_model=PersonalRecordResponse)
def get_personal_record(user_id: UUID, db: DbSession, _api_key: ApiKeyDep):
    """Return the user's personal_record (404 if none exists)."""
    return personal_record_service.get_for_user(db, user_id, raise_404=True)


@router.put("/users/{user_id}/personal-record", response_model=PersonalRecordResponse)
def upsert_personal_record(
    user_id: UUID,
    payload: PersonalRecordUpsert,
    db: DbSession,
    response: Response,
    _api_key: ApiKeyDep,
):
    """Create or update the user's personal_record. 201 on create, 200 on update."""
    record, created = personal_record_service.upsert(db, user_id, payload)
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return record
