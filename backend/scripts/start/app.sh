#!/bin/bash
set -e -x

# Init database
echo 'Applying migrations...'
uv run alembic upgrade head

# Initialize provider settings
echo 'Initializing provider settings...'
uv run python scripts/init_provider_settings.py

# Initialize device priority table
echo 'Initializing priorities...'
uv run python scripts/init_device_priorities.py

# Seed admin account (uses ADMIN_EMAIL/ADMIN_PASSWORD env vars, or defaults)
echo 'Seeding admin account...'
uv run python scripts/init/seed_admin.py

# Initialize series type definitions
echo 'Initializing series type definitions...'
uv run python scripts/init/seed_series_types.py

# Initialize archival settings
echo 'Initializing archival settings...'
uv run python scripts/init/seed_archival_settings.py

# Init app
echo "Starting the FastAPI application..."
if [ "$ENVIRONMENT" = "local" ]; then
    uv run fastapi dev app/main.py --host 0.0.0.0 --port 8000
else
    uv run fastapi run app/main.py --host 0.0.0.0 --port 8000
fi
