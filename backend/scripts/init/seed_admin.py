#!/usr/bin/env python3
"""Seed default admin developer account if it doesn't exist."""

from app.config import settings
from app.database import SessionLocal
from app.schemas.developer import DeveloperCreate
from app.services import developer_service


def seed_admin(email: str, password: str) -> None:
    """Create default admin developer if it doesn't exist."""
    with SessionLocal() as db:
        existing = developer_service.crud.get_all(
            db,
            filters={},
            offset=0,
            limit=1,
            sort_by=None,
        )
        if existing:
            print("A developer account already exists, skipping admin seed.")
            return

        developer_service.register(db, DeveloperCreate(email=email, password=password))
        print(f"✓ Created default admin developer: {email}")


if __name__ == "__main__":
    seed_admin(settings.admin_email, settings.admin_password.get_secret_value())
