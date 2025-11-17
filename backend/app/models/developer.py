from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTableUUID
from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import datetime_tz


class Developer(BaseDbModel, SQLAlchemyBaseUserTableUUID):
    """Admin of the portal model"""

    created_at: Mapped[datetime_tz]
    updated_at: Mapped[datetime_tz]
