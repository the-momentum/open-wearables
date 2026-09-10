from datetime import datetime

from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import FKUser, PrimaryKey, str_32, str_64


class DataTypeCoverage(BaseDbModel):
    """What data we currently hold, per user, provider and data type.

    ``coverage_end`` moving means live sync is delivering, ``coverage_start`` moving means
    a backfill is filling history in, and ``last_written_at`` moving while neither range
    does means the provider is re-sending data we already hold. A type that silently stops
    arriving is the case no run-level signal catches: runs just stop mentioning it.
    """

    __tablename__ = "data_type_coverage"

    user_id: Mapped[PrimaryKey[FKUser]]
    provider: Mapped[PrimaryKey[str_64]]
    # A SeriesType slug for series, an event record's category for events.
    data_type: Mapped[PrimaryKey[str_64]]
    # series | event -- which of those data_type is.
    kind: Mapped[str_32]

    coverage_start: Mapped[datetime]
    coverage_end: Mapped[datetime]
    last_written_at: Mapped[datetime]
