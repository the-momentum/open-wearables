from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import PrimaryKey, Unique, str_10
from app.schemas.enums import SeriesType


class SeriesTypeDefinition(BaseDbModel):
    """Defines the available time-series types and their canonical units."""

    __tablename__ = "series_type_definition"

    id: Mapped[PrimaryKey[int]]
    code: Mapped[Unique[SeriesType]]
    unit: Mapped[str_10]
