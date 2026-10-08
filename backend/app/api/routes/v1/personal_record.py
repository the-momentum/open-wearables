from typing import Any
from uuid import UUID

from fastapi import APIRouter

from app.database import DbSession
from app.schemas.model_crud.activities import PersonalRecordResponse, PersonalRecordUpdate
from app.services import ApiKeyDep
from app.services.personal_record_service import personal_record_service

router = APIRouter()

# Request validation errors come back as 400, not FastAPI's default 422 (see main.py).
_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {
        "description": "Validation error",
        "content": {"application/json": {"example": {"detail": "Input should be a valid UUID"}}},
    },
    404: {
        "description": "User not found",
        "content": {
            "application/json": {"example": {"detail": "User with ID: 123e4567-e89b-12d3-a456-426614174000 not found."}}
        },
    },
}


@router.get("/users/{user_id}/personal-record", response_model=PersonalRecordResponse, responses=_RESPONSES)
def get_personal_record(user_id: UUID, db: DbSession, _api_key: ApiKeyDep):
    """Returns the user's birth date, gender and sex. A field that was never set is null."""
    return personal_record_service.get_for_user(db, user_id)


@router.put(
    "/users/{user_id}/personal-record",
    response_model=PersonalRecordResponse,
    responses={
        **_RESPONSES,
        400: {
            "description": "Validation error",
            "content": {"application/json": {"example": {"detail": "birth_date cannot be in the future"}}},
        },
    },
)
def put_personal_record(user_id: UUID, payload: PersonalRecordUpdate, db: DbSession, _api_key: ApiKeyDep):
    """Sets the user's birth date, gender and sex.

    Replaces the whole record: a field left out of the body is set to null. Open Wearables uses
    the birth date for the user's age, for example in the body summary and for the maximum heart
    rate behind the intensity minutes of the activity summary.
    """
    return personal_record_service.upsert_for_user(db, user_id, payload)
