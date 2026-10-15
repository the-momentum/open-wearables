from logging import Logger, getLogger
from uuid import UUID

from app.database import DbSession
from app.models import PersonalRecord
from app.repositories import PersonalRecordRepository
from app.schemas.model_crud.activities import PersonalRecordCreate, PersonalRecordUpdate, sex_to_db
from app.services.services import AppService
from app.services.user_service import user_service
from app.utils.exceptions import handle_exceptions


class PersonalRecordService(
    AppService[PersonalRecordRepository, PersonalRecord, PersonalRecordCreate, PersonalRecordUpdate]
):
    def __init__(self, log: Logger, **kwargs):
        super().__init__(
            crud_model=PersonalRecordRepository,
            model=PersonalRecord,
            log=log,
            **kwargs,
        )

    @handle_exceptions
    def get_for_user(self, db_session: DbSession, user_id: UUID) -> PersonalRecord:
        """The user's record. Without one, an unsaved empty record, so every field reads as null."""
        user_service.get(db_session, user_id, raise_404=True)
        return self.crud.get_by_user_id(db_session, user_id) or PersonalRecord(user_id=user_id)

    @handle_exceptions
    def upsert_for_user(self, db_session: DbSession, user_id: UUID, payload: PersonalRecordUpdate) -> PersonalRecord:
        """Create the user's record or replace it: a field left out of the payload becomes null."""
        user_service.get(db_session, user_id, raise_404=True)
        return self.crud.upsert(
            db_session,
            user_id,
            birth_date=payload.birth_date,
            gender=payload.gender,
            sex=sex_to_db(payload.sex),
        )


personal_record_service = PersonalRecordService(log=getLogger(__name__))
