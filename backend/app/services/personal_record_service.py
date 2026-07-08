from logging import Logger, getLogger
from uuid import UUID, uuid4

from app.database import DbSession
from app.models import PersonalRecord
from app.repositories.personal_record_repository import PersonalRecordRepository
from app.schemas.model_crud.activities import PersonalRecordCreate, PersonalRecordUpsert
from app.services.services import AppService
from app.services.user_service import user_service
from app.utils.exceptions import ResourceNotFoundError, handle_exceptions


class PersonalRecordService(
    AppService[PersonalRecordRepository, PersonalRecord, PersonalRecordCreate, PersonalRecordUpsert]
):
    def __init__(self, log: Logger, **kwargs):
        super().__init__(
            crud_model=PersonalRecordRepository,
            model=PersonalRecord,
            log=log,
            **kwargs,
        )

    @handle_exceptions
    def get_for_user(
        self,
        db_session: DbSession,
        user_id: UUID,
        raise_404: bool = False,
    ) -> PersonalRecord | None:
        record = self.crud.get_by_user_id(db_session, user_id)
        if not record and raise_404:
            raise ResourceNotFoundError(self.name, user_id)
        return record

    @handle_exceptions
    def upsert(
        self,
        db_session: DbSession,
        user_id: UUID,
        payload: PersonalRecordUpsert,
    ) -> tuple[PersonalRecord, bool]:
        # 404 if the user does not exist (avoids an opaque FK violation).
        # NB: user_service.get is wrapped by @handle_exceptions, which converts a
        # raise_404 ResourceNotFoundError into a FastAPI HTTPException. We instead
        # probe with a plain get (returns None when absent) and raise
        # ResourceNotFoundError ourselves so callers get the domain exception.
        if user_service.get(db_session, user_id) is None:
            raise ResourceNotFoundError("user", user_id)

        existing = self.crud.get_by_user_id(db_session, user_id)
        if existing is None:
            creator = PersonalRecordCreate(id=uuid4(), user_id=user_id, **payload.model_dump())
            return self.crud.create(db_session, creator), True

        return self.crud.update(db_session, existing, payload), False


personal_record_service = PersonalRecordService(log=getLogger(__name__))
