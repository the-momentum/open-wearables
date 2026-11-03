"""sensorbio sleep window durations

Revision ID: 5d2b8e41c7a3
Revises: e9413ac05e3b

Sets duration_seconds and sleep_time_in_bed_minutes of stored Sensor Bio sleep sessions to the
start-to-end window, as new syncs store them. Starts from data_source, so an instance without
Sensor Bio sources updates nothing. downgrade does not restore the old values.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5d2b8e41c7a3"
down_revision: Union[str, None] = "e9413ac05e3b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

WINDOW_SECONDS = "EXTRACT(EPOCH FROM er.end_datetime - er.start_datetime)::int"


def upgrade() -> None:
    op.execute(
        f"""
        UPDATE event_record er
        SET duration_seconds = {WINDOW_SECONDS}
        FROM data_source ds
        WHERE ds.provider = 'sensorbio'
          AND er.data_source_id = ds.id
          AND er.category = 'sleep'
          AND er.end_datetime > er.start_datetime
          AND er.duration_seconds IS DISTINCT FROM {WINDOW_SECONDS}
        """
    )
    op.execute(
        f"""
        UPDATE sleep_details sd
        SET sleep_time_in_bed_minutes = {WINDOW_SECONDS} / 60
        FROM event_record er
        JOIN data_source ds ON ds.id = er.data_source_id
        WHERE ds.provider = 'sensorbio'
          AND er.category = 'sleep'
          AND er.end_datetime > er.start_datetime
          AND sd.record_id = er.id
          AND sd.sleep_time_in_bed_minutes IS DISTINCT FROM {WINDOW_SECONDS} / 60
        """
    )


def downgrade() -> None:
    pass
