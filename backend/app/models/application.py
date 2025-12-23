from uuid import UUID

from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import FKDeveloper, PrimaryKey, Unique, datetime_tz, str_64, str_100


class Application(BaseDbModel):
    """SDK Application for external mobile apps to authenticate users."""

    id: Mapped[PrimaryKey[UUID]]
    app_id: Mapped[Unique[str_64]]
    app_secret_hash: Mapped[str]  # bcrypt hashed secret
    name: Mapped[str_100]  # Display name
    developer_id: Mapped[FKDeveloper]  # Owner developer
    created_at: Mapped[datetime_tz]
    updated_at: Mapped[datetime_tz]
