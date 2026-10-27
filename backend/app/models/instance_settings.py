from datetime import datetime

from sqlalchemy import CheckConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import BaseDbModel
from app.mappings import PrimaryKey, email, str_100


class InstanceSettings(BaseDbModel):
    """How this instance presents itself to end users, e.g. in the Open Wearables Connect app.

    Singleton table - exactly one row with id=1 enforced by a CHECK constraint.

    - organization_name: shown to a user before they share data ("Connect to Acme Health?").
    - logo_url: absolute https URL of the organisation's logo.
    - support_email: where users are told to write when something is wrong on the instance side.
    - privacy_policy_url, terms_url: the organisation's own documents, shown in the app before connecting.
      Optional - a self-hosted instance for personal use has no one else's data to account for.
    - require_acceptance: the app asks users to accept the documents and reports it (LegalAcceptance).
    - legal_documents_version: bumped when a document URL changes or by hand; the app asks again
      when the version it accepted is not the current one.
    """

    __tablename__ = "instance_settings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_instance_settings_singleton"),)

    id: Mapped[PrimaryKey[int]]
    organization_name: Mapped[str_100 | None]
    logo_url: Mapped[str | None]
    support_email: Mapped[email | None]
    privacy_policy_url: Mapped[str | None]
    terms_url: Mapped[str | None]
    require_acceptance: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    legal_documents_version: Mapped[int] = mapped_column(default=1, server_default=text("1"))
    updated_at: Mapped[datetime | None]
