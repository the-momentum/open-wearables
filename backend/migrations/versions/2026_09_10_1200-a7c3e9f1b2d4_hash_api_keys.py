"""hash_api_keys

Store API keys as SHA-256 hashes with a display prefix instead of the raw value,
and switch the primary key from the raw key string to a UUID.

Revision ID: a7c3e9f1b2d4
Revises: cf76dead11f5

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7c3e9f1b2d4"
down_revision: Union[str, None] = "cf76dead11f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("api_key", sa.Column("uuid_id", sa.UUID(), nullable=True))
    op.add_column("api_key", sa.Column("key_hash", sa.String(length=64), nullable=True))
    op.add_column("api_key", sa.Column("key_prefix", sa.String(length=10), nullable=True))

    # Existing rows hold the raw key in "id": hash it in place so no key stops working.
    op.execute(
        """
        UPDATE api_key
        SET uuid_id = gen_random_uuid(),
            key_hash = encode(sha256(convert_to(id, 'UTF8')), 'hex'),
            key_prefix = left(id, 10)
        """
    )

    op.alter_column("api_key", "uuid_id", nullable=False)
    op.alter_column("api_key", "key_hash", nullable=False)
    op.alter_column("api_key", "key_prefix", nullable=False)

    op.drop_constraint("api_key_pkey", "api_key", type_="primary")
    op.drop_column("api_key", "id")
    op.alter_column("api_key", "uuid_id", new_column_name="id")
    op.create_primary_key("api_key_pkey", "api_key", ["id"])
    op.create_unique_constraint("api_key_key_hash_key", "api_key", ["key_hash"])


def downgrade() -> None:
    # The raw key values are gone for good, so the old string primary key cannot be restored.
    # Rows are dropped: after downgrading, developers must generate new keys.
    op.execute("DELETE FROM api_key")

    op.drop_constraint("api_key_key_hash_key", "api_key", type_="unique")
    op.drop_constraint("api_key_pkey", "api_key", type_="primary")
    op.drop_column("api_key", "id")
    op.drop_column("api_key", "key_prefix")
    op.drop_column("api_key", "key_hash")
    op.add_column("api_key", sa.Column("id", sa.String(length=64), nullable=False))
    op.create_primary_key("api_key_pkey", "api_key", ["id"])
