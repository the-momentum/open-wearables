#!/usr/bin/env python3
"""Seed default admin developer account if it doesn't exist."""

from app.database import SessionLocal
from app.schemas.developer import DeveloperCreate
from app.services import developer_service

ADMIN_EMAIL = "admin@admin.com"
ADMIN_PASSWORD = "secret123"


def seed_admin() -> None:
    """Create default admin developer if it doesn't exist."""
    db = SessionLocal()
    try:
        existing = developer_service.crud.get_all(
            db,
            filters={"email": ADMIN_EMAIL},
            offset=0,
            limit=1,
            sort_by=None,
        )
        if existing:
            print(f"Admin developer {ADMIN_EMAIL} already exists, skipping.")
            return

        developer_service.register(db, DeveloperCreate(email=ADMIN_EMAIL, password=ADMIN_PASSWORD))
        print(f"✓ Created default admin developer: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
    except Exception as exc:
        db.rollback()
        raise exc
    finally:
        db.close()


if __name__ == "__main__":
    seed_admin()
