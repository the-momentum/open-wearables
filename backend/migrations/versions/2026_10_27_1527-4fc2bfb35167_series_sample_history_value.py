"""series sample history value

Revision ID: 4fc2bfb35167
Revises: 6c49f0f8fba2

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4fc2bfb35167"
down_revision: Union[str, None] = "6c49f0f8fba2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable without a default: added to the catalog only, the table is not rewritten.
    op.add_column("series_sample", sa.Column("history_value", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("series_sample", "history_value")
