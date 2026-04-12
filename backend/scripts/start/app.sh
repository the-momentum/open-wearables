#!/bin/bash
set -e -x

# Load auto-generated Svix JWT secret from the shared Docker volume (if present)
if [ -f /run/svix-secrets/jwt_secret ]; then
    SVIX_JWT_SECRET=$(cat /run/svix-secrets/jwt_secret)
    export SVIX_JWT_SECRET
fi

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

# Register webhook event types with Svix (with retry, non-fatal)
echo 'Registering webhook event types...'
for i in 1 2 3; do
    uv run python scripts/init/seed_webhook_event_types.py && break
    echo "Svix not ready yet, retrying in 5s... (attempt ${i}/3)"
    sleep 5
done || echo "Warning: Could not register webhook event types with Svix. Will retry on next startup."

# Init app
echo "Starting the FastAPI application..."
if [ "$ENVIRONMENT" = "local" ]; then
    uv run fastapi dev app/main.py --host 0.0.0.0 --port 8000
else
    uv run fastapi run app/main.py --host 0.0.0.0 --port 8000
fi
