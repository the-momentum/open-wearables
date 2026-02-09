"""add_refresh_token_table

Revision ID: a1b2c3d4e5f6
Revises: 0e8f0a9be2cc

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "0e8f0a9be2cc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "refresh_token",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("token_type", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("app_id", sa.String(length=64), nullable=True),
        sa.Column("developer_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["developer_id"], ["developer.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_refresh_token_user_id", "refresh_token", ["user_id"], unique=False)
    op.create_index("idx_refresh_token_developer_id", "refresh_token", ["developer_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_refresh_token_developer_id", table_name="refresh_token")
    op.drop_index("idx_refresh_token_user_id", table_name="refresh_token")
    op.drop_table("refresh_token")
