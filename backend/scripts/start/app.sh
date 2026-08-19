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

# Initialize series type definitions
echo 'Initializing series type definitions...'
uv run python scripts/init/seed_series_types.py


# TODO: Remove this after ~2026-09-01 once all deployments have migrated.
# Relabels Oura HRV stored as SDNN (id=3) to RMSSD (id=7); scoped to provider='oura', no-op once corrected.
echo 'Running Oura HRV SDNN->RMSSD relabel...'
uv run python scripts/data_migrations/relabel_oura_hrv_sdnn_to_rmssd.py \
    || echo "Warning: Oura HRV relabel failed — will retry on next startup."


# TODO: Remove this after ~2026-09-01 once all deployments have migrated.
# Labels is_daily_total on archival data_point_series (daily totals → TRUE); idempotent,
# only flips NULL rows, batched. After the first full pass, re-runs are no-ops.
echo 'Running is_daily_total backfill...'
uv run python scripts/data_migrations/backfill_is_daily_total.py \
    || echo "Warning: is_daily_total backfill failed — will retry on next startup."

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
    uv run fastapi dev app/main.py --host 0.0.0.0 --port "${API_PORT:-8000}"
else
    uv run fastapi run app/main.py --host 0.0.0.0 --port "${API_PORT:-8000}"
fi
