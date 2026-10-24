from datetime import datetime, timezone
from typing import Any

from sqlalchemy.exc import IntegrityError

from app.database import DbSession
from app.models import InstanceSettings


class InstanceSettingsRepository:
    """Data access for the singleton instance_settings row."""

    def get(self, db: DbSession) -> InstanceSettings | None:
        return db.get(InstanceSettings, 1)

    def update(self, db: DbSession, changes: dict[str, Any]) -> InstanceSettings:
        settings = self.get(db) or self._create(db)
        for field, value in changes.items():
            setattr(settings, field, value)
        settings.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(settings)
        return settings

    def _create(self, db: DbSession) -> InstanceSettings:
        settings = InstanceSettings(id=1, created_at=datetime.now(timezone.utc))
        db.add(settings)
        try:
            db.flush()
        except IntegrityError:
            # Another request created the row concurrently - use theirs.
            db.rollback()
            existing = self.get(db)
            if existing is None:  # pragma: no cover - only on DB failure
                raise
            return existing
        return settings
