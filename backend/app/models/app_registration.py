from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint
from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import PrimaryKey, email, str_50


class AppRegistration(BaseDbModel):
    """Registration of this instance with the Open Wearables Connect license server.

    Singleton table - at most one row with id=1, created when an administrator registers.

    - instance_id: random id sent to the license server, separate from the telemetry id.
    - private_key: base64url Ed25519 seed; signs instance tokens and seat requests. Never sent anywhere.
    - hmac_secret: key of the pseudonymous user ids the license server sees. Never sent anywhere.
    - status: last status reported by the license server (pending_verification, active, removed).
    """

    __tablename__ = "app_registration"
    __table_args__ = (CheckConstraint("id = 1", name="ck_app_registration_singleton"),)

    id: Mapped[PrimaryKey[int]]
    instance_id: Mapped[UUID]
    private_key: Mapped[str]
    hmac_secret: Mapped[str]
    admin_email: Mapped[email]
    marketing_consent: Mapped[bool]
    terms_version: Mapped[str_50]
    status: Mapped[str_50]
    email_verified_at: Mapped[datetime | None]
    status_checked_at: Mapped[datetime | None]
