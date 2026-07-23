from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint
from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import PrimaryKey


class TelemetryState(BaseDbModel):
    """Local state of anonymous usage telemetry.

    Singleton table - exactly one row with id=1 enforced by a CHECK constraint.

    - instance_id: random UUID generated on first use. Identifies this
      installation anonymously; survives restarts and secret rotations.
    - created_at: when telemetry first ran here (approximates instance age).
    - last_sent_at: last successful ping delivery, used for debouncing.
    """

    __tablename__ = "telemetry_state"
    __table_args__ = (CheckConstraint("id = 1", name="ck_telemetry_state_singleton"),)

    id: Mapped[PrimaryKey[int]]
    instance_id: Mapped[UUID]
    created_at: Mapped[datetime]
    last_sent_at: Mapped[datetime | None]
