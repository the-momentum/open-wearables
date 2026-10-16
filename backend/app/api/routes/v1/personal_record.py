from uuid import UUID

from fastapi import APIRouter

from app.database import DbSession
from app.schemas.model_crud.activities import PersonalRecordResponse, PersonalRecordUpdate
from app.services import ApiKeyDep
from app.services.personal_record_service import personal_record_service

router = APIRouter()


@router.get("/users/{user_id}/personal-record")
def get_personal_record(user_id: UUID, db: DbSession, _api_key: ApiKeyDep) -> PersonalRecordResponse:
    """Returns the user's birth date, gender and sex. A field that was never set is null."""
    return PersonalRecordResponse.model_validate(personal_record_service.get_for_user(db, user_id))


@router.put("/users/{user_id}/personal-record")
def put_personal_record(
    user_id: UUID,
    payload: PersonalRecordUpdate,
    db: DbSession,
    _api_key: ApiKeyDep,
) -> PersonalRecordResponse:
    """Sets the user's birth date, gender and sex.

    Replaces the whole record: a field left out of the body is set to null. Open Wearables uses
    the birth date for the user's age, for example in the body summary and for the maximum heart
    rate behind the intensity minutes of the activity summary.
    """
    return PersonalRecordResponse.model_validate(personal_record_service.upsert_for_user(db, user_id, payload))
