from uuid import UUID

from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import FKDeveloper, PrimaryKey, Unique, str_10, str_64


class ApiKey(BaseDbModel):
    """Global API key for external service access.

    The raw key value is never stored: only its SHA-256 hash (for lookup) and a short
    prefix (for display). The full value is returned once, on create or rotate.
    """

    __tablename__ = "api_key"

    id: Mapped[PrimaryKey[UUID]]
    key_hash: Mapped[Unique[str_64]]  # sha256 hex digest of the raw key
    key_prefix: Mapped[str_10]  # first characters of the raw key, shown in the UI
    name: Mapped[str]
    created_by: Mapped[FKDeveloper | None]
