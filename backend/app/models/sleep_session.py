from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import BaseDbModel


class SleepSession(BaseDbModel):
    """In-progress (not-yet-finalized) sleep session state for a user.

    Postgres replacement for the Redis ``sleep:active:{user_id}`` blob and the
    ``sleep:active_users`` set, used when running without Redis
    (``task_execution_mode="inline"``). One row per user: it is created/updated as
    sleep stages accumulate and deleted by ``finish_sleep`` once the session is
    persisted as an ``event_record``. ``start_time``/``end_time`` mirror the
    session window so stale sessions can be queried without deserialising ``state``.
    """

    __tablename__ = "sleep_session"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), primary_key=True)
    state: Mapped[dict[str, Any]] = mapped_column(JSONB)
    start_time: Mapped[datetime]
    end_time: Mapped[datetime]
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
