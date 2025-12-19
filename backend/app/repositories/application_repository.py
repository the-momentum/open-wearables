from uuid import UUID

from app.database import DbSession
from app.models import Application
from app.repositories.repositories import CrudRepository
from app.schemas.application import ApplicationCreateInternal, ApplicationUpdate


class ApplicationRepository(CrudRepository[Application, ApplicationCreateInternal, ApplicationUpdate]):
    def __init__(self, model: type[Application]):
        super().__init__(model)

    def get_by_app_id(self, db_session: DbSession, app_id: str) -> Application | None:
        """Get application by public app_id."""
        return db_session.query(self.model).filter(self.model.app_id == app_id).one_or_none()

    def list_by_developer(self, db_session: DbSession, developer_id: UUID) -> list[Application]:
        """List all applications for a specific developer."""
        return (
            db_session.query(self.model)
            .filter(self.model.developer_id == developer_id)
            .order_by(self.model.created_at.desc())
            .all()
        )

    def get_all_ordered(self, db_session: DbSession) -> list[Application]:
        """Get all applications ordered by creation date descending."""
        return db_session.query(self.model).order_by(self.model.created_at.desc()).all()
