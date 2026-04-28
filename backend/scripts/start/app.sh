#!/bin/bash
set -e -x

# Ensure svix database exists (idempotent)
echo 'Ensuring svix database...'
uv run python scripts/init/create_svix_db.py

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

# Seed agent internal API key — only in local dev or when explicitly configured
if [ "${ENVIRONMENT:-}" = "local" ] || [ -n "${AGENT_API_KEY:-}" ]; then
    echo 'Seeding agent API key...'
    uv run python scripts/init/seed_agent_api_key.py
else
    echo 'Skipping agent API key seed; AGENT_API_KEY is not configured.'
fi

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
