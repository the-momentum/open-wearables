from sqlalchemy.orm import Mapped, mapped_column

from app.database import BaseDbModel
from app.mappings import PrimaryKey, str_64


class SeriesTypeDefinition(BaseDbModel):
    """Defines the available time-series types and their canonical units."""

    __tablename__ = "series_type_definition"

    id: Mapped[PrimaryKey[int]]
    code: Mapped[str_64] = mapped_column(unique=True)
    unit: Mapped[str_64]

