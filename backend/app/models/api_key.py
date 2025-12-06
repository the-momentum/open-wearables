from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import FKDeveloper, PrimaryKey, datetime_tz, str_64


class ApiKey(BaseDbModel):
    """Global API key for external service access."""

    id: Mapped[PrimaryKey[str_64]]  # The actual key value (sk-...)
    name: Mapped[str]
    created_by: Mapped[FKDeveloper | None]
    created_at: Mapped[datetime_tz]
