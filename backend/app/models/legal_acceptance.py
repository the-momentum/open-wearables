from datetime import datetime
from uuid import UUID

from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import FKUser, PrimaryKey


class LegalAcceptance(BaseDbModel):
    """A user accepted a version of the instance's legal documents in the Open Wearables Connect app.

    Append-only audit trail, one row per user and version.

    - documents_version: InstanceSettings.legal_documents_version that was shown.
    - privacy_policy_url, terms_url: what that version pointed to, kept in case the settings change.
    - accepted_at: when the user ticked the box, from the phone; created_at is when it arrived.
    """

    __tablename__ = "legal_acceptance"
    __table_args__ = (UniqueConstraint("user_id", "documents_version", name="uq_legal_acceptance_user_version"),)

    id: Mapped[PrimaryKey[UUID]]
    user_id: Mapped[FKUser]
    documents_version: Mapped[int]
    privacy_policy_url: Mapped[str | None]
    terms_url: Mapped[str | None]
    accepted_at: Mapped[datetime]
