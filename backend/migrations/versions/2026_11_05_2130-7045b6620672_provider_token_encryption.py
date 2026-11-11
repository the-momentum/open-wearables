"""provider token encryption

Revision ID: 7045b6620672
Revises: 3f6b9c2d8e41

Records when this release reached the database and a fingerprint (HMAC) of its SECRET_KEY; seven days later the app
starts encrypting provider OAuth tokens and webhook secrets (app/utils/token_encryption.py).

The downgrade decrypts them all and drops the marker, with its own frozen copy of the format so later app changes
can't break it. A token in a later release's format stops it, since the earlier release would take it for plaintext.
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

# Frozen copy of the stored format: "§enc:v1:" + Fernet token, key = HMAC-SHA256(SECRET_KEY, purpose). Every
# encrypted format starts with "§", outside the printable ASCII that OAuth tokens are made of.
ENCRYPTED_MARK = "\u00a7"  # "§"
ENCRYPTED_PREFIX = f"{ENCRYPTED_MARK}enc:v1:"
KEY_PURPOSE = b"provider-token-encryption"
KEY_CHECK_PURPOSE = b"provider-token-key-check"
BATCH_SIZE = 500
# Passes catch values written encrypted meanwhile, except to rows already decrypted: the beat task decrypts those
MAX_PASSES = 5

# The encrypted columns, after their table's key
_SECRET_COLUMNS = (
    ("user_connection", "id", "access_token", "refresh_token"),
    ("provider_settings", "provider", "webhook_secret"),
)


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
        raise RuntimeError("Decrypting the provider secrets needs a database connection: run the downgrade online.")
    # First: the table's lock holds the app's marker lookups until this commits, and they then find no marker
    op.drop_table("provider_token_encryption")
    _decrypt_all(op.get_bind())


def _fernet() -> Fernet:
    return Fernet(urlsafe_b64encode(hmac.new(settings.secret_key.encode(), KEY_PURPOSE, sha256).digest()))


def _decrypt(fernet: Fernet, value: str | None) -> str | None:
    if value is None or not value.startswith(ENCRYPTED_MARK):
        return value
    if not value.startswith(ENCRYPTED_PREFIX):
        raise RuntimeError(
            "A provider secret is stored in a later release's format. Downgrade the database with that release first."
        )
    try:
        return fernet.decrypt(value.removeprefix(ENCRYPTED_PREFIX)).decode()
    except (InvalidToken, ValueError):
        raise RuntimeError(
            "A provider secret can't be decrypted with the configured SECRET_KEY. "
            "Run the downgrade with the SECRET_KEY it was encrypted with."
        ) from None


def _decrypt_all(connection: sa.Connection) -> None:
    fernet = _fernet()
    for _ in range(MAX_PASSES):
        if not sum(_decrypt_pass(connection, fernet, *columns) for columns in _SECRET_COLUMNS):
            return
    raise RuntimeError(
        "Provider secrets kept being written encrypted during the downgrade. "
        "Stop the API, worker and beat, then run the downgrade again."
    )


def _decrypt_pass(connection: sa.Connection, fernet: Fernet, table_name: str, key_name: str, *names: str) -> int:
    """Decrypt the encrypted values of a table in batches; the number of rows that had any."""
    table = sa.table(table_name, sa.column(key_name), *(sa.column(name) for name in names))
    key, values = table.c[key_name], [table.c[name] for name in names]
    # Any encrypted format, so one of a later release stops the downgrade instead of staying behind
    encrypted = sa.or_(*(sa.func.starts_with(value, ENCRYPTED_MARK) for value in values))
    found = 0
    after_key = None
    while True:
        query = sa.select(key, *values).where(encrypted)
        if after_key is not None:
            query = query.where(key > after_key)
        rows = connection.execute(query.order_by(key).limit(BATCH_SIZE)).all()
        if not rows:
            return found
        found += len(rows)
        for row_key, *stored in rows:
            # Only while the row still holds what was read: a value written meanwhile is read again next pass
            connection.execute(
                sa.update(table)
                .where(key == row_key, *(value.is_not_distinct_from(old) for value, old in zip(values, stored)))
                .values({value: _decrypt(fernet, old) for value, old in zip(values, stored)})
            )
        after_key = rows[-1][0]
