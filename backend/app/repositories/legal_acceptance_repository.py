from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError

from app.database import DbSession
from app.models import LegalAcceptance


class LegalAcceptanceRepository:
    """Data access for the users' acceptances of the instance's legal documents."""

    def get(self, db: DbSession, user_id: UUID, documents_version: int) -> LegalAcceptance | None:
        return (
            db.query(LegalAcceptance)
            .filter(LegalAcceptance.user_id == user_id, LegalAcceptance.documents_version == documents_version)
            .one_or_none()
        )

    def list_for_user(self, db: DbSession, user_id: UUID) -> list[LegalAcceptance]:
        return (
            db.query(LegalAcceptance)
            .filter(LegalAcceptance.user_id == user_id)
            .order_by(LegalAcceptance.documents_version.desc())
            .all()
        )

    def create(
        self,
        db: DbSession,
        user_id: UUID,
        documents_version: int,
        privacy_policy_url: str | None,
        terms_url: str | None,
        accepted_at: datetime,
    ) -> LegalAcceptance | None:
        """The new row, or None when one for this user and version already exists (a concurrent retry)."""
        acceptance = LegalAcceptance(
            id=uuid4(),
            user_id=user_id,
            documents_version=documents_version,
            privacy_policy_url=privacy_policy_url,
            terms_url=terms_url,
            accepted_at=accepted_at,
        )
        db.add(acceptance)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return None
        db.refresh(acceptance)
        return acceptance
