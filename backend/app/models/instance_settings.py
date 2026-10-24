from datetime import datetime

from sqlalchemy import CheckConstraint
from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import PrimaryKey, email, str_100


class InstanceSettings(BaseDbModel):
    """How this instance presents itself to end users, e.g. in the Open Wearables Connect app.

    Singleton table - exactly one row with id=1 enforced by a CHECK constraint.

    - organization_name: shown to a user before they share data ("Connect to Acme Health?").
    - logo_url: absolute https URL of the organisation's logo.
    - support_email: where users are told to write when something is wrong on the instance side.
    """

    __tablename__ = "instance_settings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_instance_settings_singleton"),)

    id: Mapped[PrimaryKey[int]]
    organization_name: Mapped[str_100 | None]
    logo_url: Mapped[str | None]
    support_email: Mapped[email | None]
    updated_at: Mapped[datetime | None]
