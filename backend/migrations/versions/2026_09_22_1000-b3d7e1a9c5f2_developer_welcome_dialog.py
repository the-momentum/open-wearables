"""developer welcome dialog

Track when a developer closed the dashboard welcome dialog so it is shown once.

Revision ID: b3d7e1a9c5f2
Revises: ef6ff24def41

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3d7e1a9c5f2"
down_revision: Union[str, None] = "ef6ff24def41"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("developer", sa.Column("welcome_dialog_seen_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("developer", "welcome_dialog_seen_at")
