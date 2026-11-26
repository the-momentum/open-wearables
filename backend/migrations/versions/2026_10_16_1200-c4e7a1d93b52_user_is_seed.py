"""user is_seed

Revision ID: c4e7a1d93b52
Revises: ca74b1b24e0a

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4e7a1d93b52"
down_revision: Union[str, None] = "ca74b1b24e0a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user", sa.Column("is_seed", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    # Users created by the seed generator before this column existed carry this first_name prefix
    op.execute("""UPDATE "user" SET is_seed = true WHERE first_name LIKE '[SEED:%'""")
    op.create_index("ix_user_is_seed", "user", ["id"], unique=False, postgresql_where=sa.text("is_seed"))


def downgrade() -> None:
    op.drop_index("ix_user_is_seed", table_name="user", postgresql_where=sa.text("is_seed"))
    op.drop_column("user", "is_seed")
