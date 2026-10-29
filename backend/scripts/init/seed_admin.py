#!/usr/bin/env python3
"""Seed default admin developer account if it doesn't exist."""

from sqlalchemy.orm import Session

from app.config import DEFAULT_ADMIN_PASSWORD, settings
from app.database import SessionLocal
from app.schemas.model_crud.user_management import DeveloperCreate, DeveloperUpdate
from app.services import developer_service
from app.utils.config_utils import EnvironmentType
from app.utils.security import verify_password


class DefaultAdminPasswordError(RuntimeError):
    """Refused to seed a production admin with the placeholder password."""


def seed_admin(email: str, password: str, *, environment: EnvironmentType = EnvironmentType.LOCAL) -> None:
    """Create default admin developer if it doesn't exist.

    Existing databases are left alone, so the check only bites where it matters:
    a fresh production database whose ADMIN_PASSWORD was never set. The one exception
    is an admin account still on the public default password: it is moved to
    ADMIN_PASSWORD once that is set, since production refuses the default at login.
    """
    with SessionLocal() as db:
        if developer_service.crud.exists_any(db):
            _rotate_default_password(db, email, password, environment)
            print("A developer account already exists, skipping admin seed.")
            return

        if environment == EnvironmentType.PRODUCTION and password == DEFAULT_ADMIN_PASSWORD:
            raise DefaultAdminPasswordError(
                "ADMIN_PASSWORD is unset (still the config default); refusing to seed a production "
                "admin with a publicly known password. Set ADMIN_PASSWORD and re-run."
            )

        developer_service.register(db, DeveloperCreate(email=email, password=password))
        print(f"✓ Created default admin developer: {email}")


def _rotate_default_password(db: Session, email: str, password: str, environment: EnvironmentType) -> None:
    admin = developer_service.get_by_email(db, email)
    if not admin or not verify_password(DEFAULT_ADMIN_PASSWORD, admin.hashed_password):
        return

    if password != DEFAULT_ADMIN_PASSWORD:
        developer_service.update_developer_info(db, admin.id, DeveloperUpdate(password=password))
        print(f"✓ Replaced the default password of {email} with ADMIN_PASSWORD")
    elif environment == EnvironmentType.PRODUCTION:
        print(
            f"WARNING: {email} still uses the public default password, which production refuses at login. "
            "Set ADMIN_PASSWORD on the backend and restart it to replace the password."
        )


if __name__ == "__main__":
    seed_admin(settings.admin_email, settings.admin_password.get_secret_value(), environment=settings.environment)
