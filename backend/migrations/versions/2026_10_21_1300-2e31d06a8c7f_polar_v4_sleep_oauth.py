"""add separate Polar AccessLink v4 sleep credentials"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "2e31d06a8c7f"
down_revision: Union[str, None] = "c4e7a1d93b52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("user_connection", sa.Column("polar_v4_access_token", sa.Text(), nullable=True))
    op.add_column("user_connection", sa.Column("polar_v4_refresh_token", sa.Text(), nullable=True))
    op.add_column("user_connection", sa.Column("polar_v4_token_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("user_connection", sa.Column("polar_v4_scope", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("user_connection", "polar_v4_scope")
    op.drop_column("user_connection", "polar_v4_token_expires_at")
    op.drop_column("user_connection", "polar_v4_refresh_token")
    op.drop_column("user_connection", "polar_v4_access_token")
