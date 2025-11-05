from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import OneToMany, datetime_tz


class User(SQLAlchemyBaseUserTableUUID, BaseDbModel):
    created_at: Mapped[datetime_tz]
    updated_at: Mapped[datetime_tz]

    workouts: Mapped[OneToMany["Workout"]]
    heart_rate_data: Mapped[OneToMany["HeartRateData"]]
    heart_rate_recovery: Mapped[OneToMany["HeartRateRecovery"]]
    active_energy: Mapped[OneToMany["ActiveEnergy"]]
    api_keys: Mapped[OneToMany["APIKey"]]
