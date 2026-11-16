"""merge fork and upstream migration heads

Revision ID: 19248cba05f6
Revises: c1e7f8ff781d, ef6ff24def41

"""
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = '19248cba05f6'
down_revision: Union[str, None] = ('c1e7f8ff781d', 'ef6ff24def41')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
