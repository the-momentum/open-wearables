#!/usr/bin/env python3
"""Seed default admin developer account if it doesn't exist."""

import argparse

from app.database import SessionLocal
from app.schemas.developer import DeveloperCreate
from app.services import developer_service

DEFAULT_EMAIL = "admin@admin.com"
DEFAULT_PASSWORD = "secret123"


def seed_admin(email: str, password: str) -> None:
    """Create default admin developer if it doesn't exist."""
    with SessionLocal() as db:
        existing = developer_service.crud.get_all(
            db,
            filters={"email": email},
            offset=0,
            limit=1,
            sort_by=None,
        )
        if existing:
            print(f"Admin developer {email} already exists, skipping.")
            return

        developer_service.register(db, DeveloperCreate(email=email, password=password))
        print(f"✓ Created default admin developer: {email}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed default admin developer account.")
    parser.add_argument("--email", default=DEFAULT_EMAIL, help="Admin email (default: admin@admin.com)")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="Admin password (default: secret123)")
    args = parser.parse_args()
    seed_admin(args.email, args.password)
