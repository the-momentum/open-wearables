"""workout_route_polyline_and_event_name

Revision ID: 7e3a9c41f2b8
Revises: 5aaff4551af6

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7e3a9c41f2b8"
down_revision: Union[str, None] = "5aaff4551af6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # GPS route encoded with the Google Encoded Polyline Algorithm (precision 5).
    # Strava already sends map.summary_polyline on every activity payload we
    # fetch; until now it was dropped during parsing.
    op.add_column("workout_details", sa.Column("route_polyline", sa.Text(), nullable=True))

    # Provider-supplied display title (e.g. Strava activity name). The public
    # Workout response always exposed a name field but it was never populated.
    op.add_column("event_record", sa.Column("name", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("event_record", "name")
    op.drop_column("workout_details", "route_polyline")
