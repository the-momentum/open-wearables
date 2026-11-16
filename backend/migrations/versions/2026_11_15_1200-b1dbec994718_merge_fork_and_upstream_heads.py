"""merge fork and upstream heads

Revision ID: b1dbec994718
Revises: 81ea20b3c94c, 3f6b9c2d8e41

"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "b1dbec994718"
down_revision: Union[str, None] = ("81ea20b3c94c", "3f6b9c2d8e41")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
