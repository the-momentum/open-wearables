from datetime import datetime, timezone
from typing import Any

from app.database import DbSession
from app.models import AppRegistration


class AppRegistrationRepository:
    """Data access for the singleton app_registration row."""

    def get(self, db: DbSession) -> AppRegistration | None:
        return db.get(AppRegistration, 1)

    def add(self, db: DbSession, fields: dict[str, Any]) -> AppRegistration:
        """Stage a new row without committing: it is kept only if the license server accepts it."""
        registration = AppRegistration(id=1, created_at=datetime.now(timezone.utc), **fields)
        db.add(registration)
        db.flush()
        return registration

    def update(self, db: DbSession, registration: AppRegistration, changes: dict[str, Any]) -> AppRegistration:
        for field, value in changes.items():
            setattr(registration, field, value)
        db.commit()
        db.refresh(registration)
        return registration

    def delete(self, db: DbSession, registration: AppRegistration) -> None:
        db.delete(registration)
        db.commit()
