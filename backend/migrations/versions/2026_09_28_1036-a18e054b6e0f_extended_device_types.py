"""extended device types

Revision ID: a18e054b6e0f
Revises: ef6ff24def41

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a18e054b6e0f"
down_revision: Union[str, None] = "ef6ff24def41"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_TYPES = ("WATCH", "BAND", "PHONE", "SCALE", "RING", "OTHER", "UNKNOWN")
NEW_TYPES = (
    "TABLET",
    "CHEST_STRAP",
    "HR_SENSOR",
    "HEADPHONES",
    "HEAD_MOUNTED",
    "GLASSES",
    "SMART_DISPLAY",
    "BP_MONITOR",
    "GLUCOSE_METER",
    "THERMOMETER",
    "SLEEP_MONITOR",
    "BIKE_COMPUTER",
    "FITNESS_MACHINE",
)


def upgrade() -> None:
    for name in NEW_TYPES:
        op.execute(f"ALTER TYPE devicetype ADD VALUE IF NOT EXISTS '{name}'")


def downgrade() -> None:
    new_values = ", ".join(f"'{name.lower()}'" for name in NEW_TYPES)
    op.execute("UPDATE data_source SET device_type = 'phone' WHERE device_type = 'tablet'")
    op.execute(f"UPDATE data_source SET device_type = 'other' WHERE device_type IN ({new_values})")

    op.execute(f"DELETE FROM device_type_priority WHERE device_type::text IN ({', '.join(repr(n) for n in NEW_TYPES)})")
    op.execute("ALTER TYPE devicetype RENAME TO devicetype_old")
    op.execute(f"CREATE TYPE devicetype AS ENUM ({', '.join(repr(n) for n in OLD_TYPES)})")
    op.execute(
        "ALTER TABLE device_type_priority ALTER COLUMN device_type TYPE devicetype USING device_type::text::devicetype"
    )
    op.execute("DROP TYPE devicetype_old")
