from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import PrimaryKey, str_100


class DataMigration(BaseDbModel):
    """A one-off data migration script that ran to completion on this instance.

    The row is written only on a clean run, so created_at (from BaseDbModel) is when it completed.
    Deleting the row makes the script run again on the next startup.
    """

    __tablename__ = "data_migration"

    name: Mapped[PrimaryKey[str_100]]
