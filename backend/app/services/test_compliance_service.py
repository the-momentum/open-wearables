"""Test file to verify AGENTS.md compliance review. DELETE after testing."""

from uuid import UUID

from sqlalchemy import select

from app.database import DbSession
from app.models.user import User
from app.schemas.user import UserRead


# Violation: service does direct DB operations (should go through repository)
# Violation: Pydantic schema used in service layer (should use SQLAlchemy models)
# Violation: not using AppService / CrudRepository pattern
class TestComplianceService:
    def get_user(self, db: DbSession, user_id: UUID) -> UserRead | None:
        result = db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user:
            return UserRead.model_validate(user)
        return None

    def list_users(self, db: DbSession) -> list[UserRead]:
        results = db.execute(select(User)).scalars().all()
        return [UserRead.model_validate(u) for u in results]


test_compliance_service = TestComplianceService()
