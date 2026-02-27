#!/usr/bin/env python3
"""Seed default archival settings (singleton logic)."""

from app.database import SessionLocal
from app.models.archival_setting import ArchivalSetting


def seed_archival_settings() -> None:
    """Create default archival settings row if not present."""
    with SessionLocal() as db:
        existing = db.query(ArchivalSetting).filter(ArchivalSetting.id == 1).first()
        if existing:
            print("Archival settings already initialized.")
            return

        # Create default empty settings (archival disabled)
        setting = ArchivalSetting(id=1, archive_after_days=None, delete_after_days=None)
        db.add(setting)
        db.commit()
        print("✓ Created default archival settings (id=1)")


if __name__ == "__main__":
    seed_archival_settings()
