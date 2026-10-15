from datetime import date
from uuid import UUID, uuid4

from sqlalchemy.dialects.postgresql import insert

from app.database import DbSession
from app.models import PersonalRecord
from app.repositories.repositories import CrudRepository
from app.schemas.model_crud.activities import PersonalRecordCreate, PersonalRecordUpdate


class PersonalRecordRepository(CrudRepository[PersonalRecord, PersonalRecordCreate, PersonalRecordUpdate]):
    def get_by_user_id(self, db_session: DbSession, user_id: UUID) -> PersonalRecord | None:
        return db_session.query(self.model).filter(self.model.user_id == user_id).one_or_none()

    def upsert(
        self,
        db_session: DbSession,
        user_id: UUID,
        birth_date: date | None,
        gender: str | None,
        sex: bool | None,
    ) -> PersonalRecord:
        """Create the user's record or replace all of its fields.

        A single INSERT ... ON CONFLICT, so two concurrent writes for a user without a record
        cannot both insert and trip the unique user_id.
        """
        stmt = insert(self.model).values(id=uuid4(), user_id=user_id, birth_date=birth_date, gender=gender, sex=sex)
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id"],
            set_={"birth_date": stmt.excluded.birth_date, "gender": stmt.excluded.gender, "sex": stmt.excluded.sex},
        )
        db_session.execute(stmt)
        db_session.commit()
        # populate_existing: a record already in the session must show the new values.
        return db_session.query(self.model).populate_existing().filter(self.model.user_id == user_id).one()
