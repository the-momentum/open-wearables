"""Ensure the agent database exists before running migrations.

Run once at container startup before `alembic upgrade head`.
Safe to re-run on existing deployments — no-ops if the database already exists.
"""

import os
import sys

import psycopg
from psycopg import sql

user = os.getenv("DB_USER", "open-wearables")
password = os.getenv("DB_PASSWORD", "open-wearables")
host = os.getenv("DB_HOST", "db")
port = os.getenv("DB_PORT", "5432")
dbname = os.getenv("DB_NAME", "agent")

try:
    with psycopg.connect(
        f"postgresql://{user}:{password}@{host}:{port}/postgres",
        autocommit=True,
    ) as conn:
        cur = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", [dbname])
        if cur.fetchone():
            print(f"Database '{dbname}' already exists.")
        else:
            conn.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(sql.Identifier(dbname), sql.Identifier(user)))
            print(f"Created database '{dbname}'.")
except psycopg.OperationalError as exc:
    print(f"Failed to connect to postgres admin DB: {exc}", file=sys.stderr)
    sys.exit(1)
