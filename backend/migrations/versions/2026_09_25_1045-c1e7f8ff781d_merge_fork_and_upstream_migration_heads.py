"""merge fork and upstream migration heads

Revision ID: c1e7f8ff781d
Revises: 9c8b7a6d5e4f, a7c3e9f1b2d4

"""
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = 'c1e7f8ff781d'
down_revision: Union[str, None] = ('9c8b7a6d5e4f', 'a7c3e9f1b2d4')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
