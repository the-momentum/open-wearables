from uuid import UUID

from app.database import DbSession
from app.models import PersonalRecord
from app.repositories.repositories import CrudRepository
from app.schemas.model_crud.activities import PersonalRecordCreate, PersonalRecordUpsert


class PersonalRecordRepository(CrudRepository[PersonalRecord, PersonalRecordCreate, PersonalRecordUpsert]):
    def __init__(self, model: type[PersonalRecord]):
        super().__init__(model)

    def get_by_user_id(self, db_session: DbSession, user_id: UUID) -> PersonalRecord | None:
        return db_session.query(self.model).filter(self.model.user_id == user_id).one_or_none()
