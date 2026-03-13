#!/usr/bin/env python3
"""Seed default archival settings (singleton logic)."""

from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models.archival_setting import ArchivalSetting


def seed_archival_settings() -> None:
    """Create default archival settings row if not present.

    Handles concurrent startup by catching IntegrityError if another
    instance inserts the row between our SELECT and INSERT.
    """
    with SessionLocal() as db:
        existing = db.query(ArchivalSetting).filter(ArchivalSetting.id == 1).first()
        if existing:
            print("Archival settings already initialized.")
            return

        setting = ArchivalSetting(id=1, archive_after_days=None, delete_after_days=None)
        db.add(setting)
        try:
            db.commit()
            print("✓ Created default archival settings (id=1)")
        except IntegrityError:
            db.rollback()
            print("Archival settings already initialized (concurrent insert).")


if __name__ == "__main__":
    seed_archival_settings()
