from sqlalchemy.ext.declarative import AbstractConcreteBase
from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import FKEventRecord


class EventRecordDetail(AbstractConcreteBase, BaseDbModel):
    """Abstract polymorphic base for detail aggregates (workout, sleep, etc.).

    There is no event_record_detail table: each concrete subclass maps to its
    own table with record_id referencing event_record directly. Queries against
    this class select a UNION ALL over the concrete detail tables.
    """

    strict_attrs = True

    # BaseDbModel autogenerates __tablename__ from the class name, which would
    # turn this abstract base back into a mapped table; suppress it.
    __tablename__ = None  # type: ignore[assignment]

    record_id: Mapped[FKEventRecord]

    @property
    def detail_type(self) -> str:
        return self.__mapper__.polymorphic_identity
