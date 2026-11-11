from sqlalchemy import CheckConstraint
from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import PrimaryKey


class ProviderTokenEncryption(BaseDbModel):
    """Singleton written by its migration: provider secrets are encrypted from created_at + ``ENCRYPTION_DELAY``
    (``app.utils.token_encryption``); without the row they stay plaintext."""

    __tablename__ = "provider_token_encryption"
    __table_args__ = (CheckConstraint("id = 1", name="ck_provider_token_encryption_singleton"),)

    id: Mapped[PrimaryKey[int]]
    # key_fingerprint() of the SECRET_KEY the migration ran with: processes with another key don't encrypt
    key_check: Mapped[str]
