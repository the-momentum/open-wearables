from app.database import DbSession
from app.models import AppSetting


class AppSettingRepository:
    """Reads/writes the singleton app_settings row (id=1)."""

    def get(self, db: DbSession) -> AppSetting:
        return db.query(AppSetting).filter(AppSetting.id == 1).one()

    def update(self, db: DbSession, setting: AppSetting) -> AppSetting:
        """Persist changes made to the given (session-attached) settings row."""
        db.commit()
        db.refresh(setting)
        return setting
