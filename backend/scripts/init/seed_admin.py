#!/usr/bin/env python3
"""Seed default admin developer account if it doesn't exist."""

from app.config import settings
from app.database import SessionLocal
from app.schemas.model_crud.user_management import DeveloperCreate
from app.services import developer_service
from app.utils.config_utils import EnvironmentType

# The placeholder in app/config.py. A production deployment that never set
# ADMIN_PASSWORD would otherwise create a publicly known admin login.
DEFAULT_ADMIN_PASSWORD = "your-secure-password"


class DefaultAdminPasswordError(RuntimeError):
    """Refused to seed a production admin with the placeholder password."""


def seed_admin(email: str, password: str, *, environment: EnvironmentType = EnvironmentType.LOCAL) -> None:
    """Create default admin developer if it doesn't exist.

    Existing databases are left alone, so the check only bites where it matters:
    a fresh production database whose ADMIN_PASSWORD was never set.
    """
    with SessionLocal() as db:
        if developer_service.crud.exists_any(db):
            print("A developer account already exists, skipping admin seed.")
            return

        if environment == EnvironmentType.PRODUCTION and password == DEFAULT_ADMIN_PASSWORD:
            raise DefaultAdminPasswordError(
                "ADMIN_PASSWORD is unset (still the config default); refusing to seed a production "
                "admin with a publicly known password. Set ADMIN_PASSWORD and re-run."
            )

        developer_service.register(db, DeveloperCreate(email=email, password=password))
        print(f"✓ Created default admin developer: {email}")


if __name__ == "__main__":
    seed_admin(settings.admin_email, settings.admin_password.get_secret_value(), environment=settings.environment)
