#!/usr/bin/env python3
"""Seed default agent API key if it doesn't exist."""

from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.database import SessionLocal
from app.schemas.model_crud.credentials import ApiKeyCreate
from app.services.api_key_service import api_key_service


def seed_agent_api_key() -> None:
    """Create default agent API key if it doesn't exist."""
    api_key_value = settings.agent_api_key.get_secret_value()
    with SessionLocal() as db:
        try:
            api_key_service.create(db, ApiKeyCreate(id=api_key_value, name="Agent (internal)"))
            print("✓ Created agent API key.")
        except IntegrityError:
            db.rollback()
            print("Agent API key already exists, skipping.")


if __name__ == "__main__":
    seed_agent_api_key()
