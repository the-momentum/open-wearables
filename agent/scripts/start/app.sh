#!/bin/bash
set -e -x

# Ensure the agent database exists (idempotent — safe on existing deployments)
echo 'Ensuring database exists...'
uv run --frozen --no-sync python scripts/postgres/ensure_db.py

# Init database
echo 'Applying migrations...'
uv run --frozen --no-sync alembic upgrade head

# Init app
echo "Starting the FastAPI application..."
if [ "$ENVIRONMENT" = "local" ]; then
    uv run --frozen --no-sync fastapi dev app/main.py --host 0.0.0.0 --port 8000
else
    uv run --frozen --no-sync fastapi run app/main.py --host 0.0.0.0 --port 8000
fi
