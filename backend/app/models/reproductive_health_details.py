from typing import ClassVar

from sqlalchemy.orm import Mapped

from app.mappings import FKEventRecord, str_32
from app.schemas.enums import EventCategory

from .event_record_detail import DetailType, EventRecordDetail


class ReproductiveHealthDetails(EventRecordDetail):
    """One reproductive health entry from a phone's health store (HealthKit, Health Connect).

    The entry's kind (`ReproductiveHealthType`) is the record's `type`. `value` is its
    normalized category value; null for entries whose presence is the whole signal.
    """

    __tablename__ = "reproductive_health_details"

    detail_type: ClassVar[DetailType] = EventCategory.REPRODUCTIVE_HEALTH
    record_id: Mapped[FKEventRecord]

    value: Mapped[str_32 | None]
    # Menstrual flow: the first day of a period (HealthKit only)
    cycle_start: Mapped[bool | None]
    # Sexual activity: whether protection was used
    protection_used: Mapped[bool | None]
    # Cervical mucus: how it feels (Health Connect only)
    cervical_mucus_sensation: Mapped[str_32 | None]
