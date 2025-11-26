from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTableUUID
from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import datetime_tz_now, datetime_tz_updated


class Developer(BaseDbModel, SQLAlchemyBaseUserTableUUID):
    """Admin of the portal model"""

    created_at: Mapped[datetime_tz_now]
    updated_at: Mapped[datetime_tz_updated]
