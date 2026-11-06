from sqlalchemy import CheckConstraint
from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import PrimaryKey


class ProviderTokenEncryption(BaseDbModel):
    """When the release that encrypts provider tokens reached this database.

    Singleton table, written only by its migration: created_at (from BaseDbModel) is when the upgrade ran, and
    provider tokens are written encrypted from ``ENCRYPTION_DELAY`` after it (``app.utils.token_encryption``).
    Without the row they stay plaintext. The migration's downgrade decrypts the tokens and drops the table.
    """

    __tablename__ = "provider_token_encryption"
    __table_args__ = (CheckConstraint("id = 1", name="ck_provider_token_encryption_singleton"),)

    id: Mapped[PrimaryKey[int]]
    # key_fingerprint() of the SECRET_KEY the migration ran with: processes with another key don't encrypt
    key_check: Mapped[str]
