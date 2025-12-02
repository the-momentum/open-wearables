#!/bin/bash
set -e -x

# Init database
echo 'Applying migrations...'
uv run alembic upgrade head

# Initialize provider settings
echo 'Initializing provider settings...'
uv run python scripts/init_provider_settings.py

# Init app
echo "Starting the FastAPI application..."
if [ "$ENVIRONMENT" = "local" ]; then
    uv run fastapi dev app/main.py --host 0.0.0.0 --port 8000
else
    uv run fastapi run app/main.py --host 0.0.0.0 --port 8000
fi
