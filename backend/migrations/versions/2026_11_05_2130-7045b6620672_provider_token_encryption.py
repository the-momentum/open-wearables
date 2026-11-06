"""provider token encryption

Revision ID: 7045b6620672
Revises: 3f6b9c2d8e41

Records when this release reached the database, and a fingerprint of the SECRET_KEY it ran with (an HMAC, which
doesn't reveal the key): a process with another key doesn't encrypt tokens. Seven days later the app writes the
provider tokens of user_connection encrypted, and a beat task encrypts the ones already stored
(app/utils/token_encryption.py).

The downgrade decrypts every token, so the previous release, which can't decrypt them, gets plaintext tokens back,
and drops the marker. It keeps its own copy of the key derivation and the decryption: it must read what this release
wrote, whatever later releases change in the app.
"""

import hmac
from base64 import urlsafe_b64encode
from hashlib import sha256
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

# revision identifiers, used by Alembic.
revision: str = "7045b6620672"
down_revision: Union[str, None] = "3f6b9c2d8e41"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Frozen copy of the stored format: "enc:v1:" + Fernet token, key = HMAC-SHA256(SECRET_KEY, purpose)
ENCRYPTED_PREFIX = "enc:v1:"
KEY_PURPOSE = b"provider-token-encryption"
KEY_CHECK_PURPOSE = b"provider-token-key-check"
BATCH_SIZE = 500
# A pass revisits the tokens a process changed while the previous one ran
MAX_PASSES = 5

_connections = sa.table("user_connection", sa.column("id"), sa.column("access_token"), sa.column("refresh_token"))
_columns = _connections.c


def upgrade() -> None:
    op.create_table(
        "provider_token_encryption",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("key_check", sa.Text(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_provider_token_encryption_singleton"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        sa.text("INSERT INTO provider_token_encryption (id, key_check) VALUES (1, :key_check)").bindparams(
            key_check=hmac.new(settings.secret_key.encode(), KEY_CHECK_PURPOSE, sha256).hexdigest()
        )
    )


def downgrade() -> None:
    if op.get_context().as_sql:
        raise RuntimeError("Decrypting the provider tokens needs a database connection: run the downgrade online.")
    # First: the table's lock holds the app's marker lookups until this commits, and they then find no marker
    op.drop_table("provider_token_encryption")
    _decrypt_all(op.get_bind())


def _fernet() -> Fernet:
    return Fernet(urlsafe_b64encode(hmac.new(settings.secret_key.encode(), KEY_PURPOSE, sha256).digest()))


def _decrypt(fernet: Fernet, value: str | None) -> str | None:
    if value is None or not value.startswith(ENCRYPTED_PREFIX):
        return value
    try:
        return fernet.decrypt(value.removeprefix(ENCRYPTED_PREFIX)).decode()
    except (InvalidToken, ValueError):
        raise RuntimeError(
            "A provider token can't be decrypted with the configured SECRET_KEY. "
            "Run the downgrade with the SECRET_KEY the tokens were encrypted with."
        ) from None


def _decrypt_all(connection: sa.Connection) -> None:
    fernet = _fernet()
    for _ in range(MAX_PASSES):
        if not _decrypt_pass(connection, fernet):
            return
    raise RuntimeError(
        "Provider tokens kept being written encrypted during the downgrade. "
        "Stop the API, worker and beat, then run the downgrade again."
    )


def _decrypt_pass(connection: sa.Connection, fernet: Fernet) -> int:
    """Decrypt the encrypted tokens in batches; the number of connections that had any."""
    encrypted = sa.or_(
        sa.func.starts_with(_columns.access_token, ENCRYPTED_PREFIX),
        sa.func.starts_with(_columns.refresh_token, ENCRYPTED_PREFIX),
    )
    found = 0
    after_id = None
    while True:
        query = sa.select(_columns.id, _columns.access_token, _columns.refresh_token).where(encrypted)
        if after_id is not None:
            query = query.where(_columns.id > after_id)
        rows = connection.execute(query.order_by(_columns.id).limit(BATCH_SIZE)).all()
        if not rows:
            return found
        found += len(rows)
        for row in rows:
            # Only while the row still holds what was read: a token refreshed meanwhile is read again next pass
            connection.execute(
                sa.update(_connections)
                .where(
                    _columns.id == row.id,
                    _columns.access_token.is_not_distinct_from(row.access_token),
                    _columns.refresh_token.is_not_distinct_from(row.refresh_token),
                )
                .values(
                    access_token=_decrypt(fernet, row.access_token), refresh_token=_decrypt(fernet, row.refresh_token)
                )
            )
        after_id = rows[-1].id
