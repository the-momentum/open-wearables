#!/usr/bin/env python3
"""Ensure the singleton app_settings row exists and backfill customized .env values.

All columns are nullable (NULL = use the config.py default), so a fresh row is empty;
backfill then copies any customized .env values in once (idempotent — see ConfigService).
"""

from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models import AppSetting
from app.services.config_service import config_service


def seed_app_settings() -> None:
    with SessionLocal() as db:
        if db.query(AppSetting).filter(AppSetting.id == 1).first() is None:
            db.add(AppSetting(id=1))
            try:
                db.commit()
                print("✓ Created app settings row (id=1)")
            except IntegrityError:
                db.rollback()
                print("App settings already initialized (concurrent insert).")

    config_service.backfill_from_env()
    print("✓ App settings backfilled from env")


if __name__ == "__main__":
    seed_app_settings()
