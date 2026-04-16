#!/usr/bin/env python3
"""Ensure the 'svix' database exists, creating it if necessary.

Runs before migrations so that svix-server can connect on first deploy.
Uses autocommit because CREATE DATABASE cannot run inside a transaction.
"""

import psycopg

from app.config import settings


def create_svix_db() -> None:
    dsn = (
        f"host={settings.db_host} "
        f"port={settings.db_port} "
        f"dbname={settings.db_name} "
        f"user={settings.db_user} "
        f"password={settings.db_password.get_secret_value()}"
    )
    with psycopg.connect(dsn, autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = 'svix'").fetchone()
        if exists:
            print("Svix database already exists, skipping.")
            return
        conn.execute("CREATE DATABASE svix")
        print("✓ Created 'svix' database.")


if __name__ == "__main__":
    create_svix_db()
