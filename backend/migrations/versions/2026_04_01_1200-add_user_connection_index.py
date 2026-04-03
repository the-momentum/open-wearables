"""add_user_connection_index

Revision ID: add_user_connection_index
Revises: f99ae82f0470

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_user_connection_index"
down_revision: Union[str, None] = "f99ae82f0470"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Add composite index on user_connection(user_id, provider) to optimize the query
    # that looks up user connections during Apple Health upload
    op.create_index(
        "idx_user_connection_user_id_provider",
        "user_connection",
        ["user_id", "provider"],
        unique=False
    )

def downgrade() -> None:
    op.drop_index("idx_user_connection_user_id_provider", table_name="user_connection")
