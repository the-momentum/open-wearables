from app.database import DbSession
from app.models import ApiKey
from app.repositories.repositories import CrudRepository
from app.schemas.model_crud.credentials import ApiKeyCreate, ApiKeyUpdate


class ApiKeyRepository(CrudRepository[ApiKey, ApiKeyCreate, ApiKeyUpdate]):
    def __init__(self, model: type[ApiKey]):
        super().__init__(model)

    def get_all_ordered(self, db_session: DbSession) -> list[ApiKey]:
        """Get all API keys ordered by creation date descending."""
        return db_session.query(self.model).order_by(self.model.created_at.desc()).all()

    def get_by_hash(self, db_session: DbSession, key_hash: str) -> ApiKey | None:
        """Look up an API key by the hash of its raw value."""
        return db_session.query(self.model).filter(self.model.key_hash == key_hash).one_or_none()
