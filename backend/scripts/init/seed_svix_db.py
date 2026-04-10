#!/usr/bin/env python3
"""Create the svix database (used by the self-hosted Svix webhook server).

Runs at application startup before migrations. Uses AUTOCOMMIT mode because
CREATE DATABASE cannot run inside a transaction. Safe to call repeatedly —
skips creation if the database already exists.
"""

from sqlalchemy import create_engine, text

from app.config import settings


def seed_svix_db() -> None:
    """Ensure the svix database exists in the shared Postgres instance."""
    # Connect to the default `postgres` maintenance DB (svix may not exist yet)
    maintenance_uri = (
        f"postgresql+psycopg://"
        f"{settings.db_user}:{settings.db_password.get_secret_value()}"
        f"@{settings.db_host}:{settings.db_port}/postgres"
    )
    engine = create_engine(maintenance_uri, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            row = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = 'svix'")).fetchone()
            if row:
                print("  svix database already exists, skipping.")
                return
            conn.execute(text("CREATE DATABASE svix"))
            print("✓ Created svix database")
    finally:
        engine.dispose()


if __name__ == "__main__":
    seed_svix_db()
