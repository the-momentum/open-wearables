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


# TODO: Remove this after ~2026-11-01 once all deployments have migrated.
# Relabels Ultrahuman temperature stored as body_temperature (id=45) to skin_temperature
# (id=46); scoped to provider='ultrahuman', no-op once corrected.
echo 'Running Ultrahuman body_temperature->skin_temperature relabel...'
uv run python scripts/data_migrations/relabel_ultrahuman_body_temp_to_skin_temp.py \
    || echo "Warning: Ultrahuman temperature relabel failed — will retry on next startup."


# TODO: Remove this after ~2026-12-01 once all deployments have migrated.
# Links legacy Whoop workout strain scores to their event records; without it they stay
# indistinguishable from the per-day cycle strain. Idempotent, no-op once linked.
echo 'Running Whoop strain event_record backfill...'
uv run python scripts/data_migrations/backfill_whoop_strain_event_record.py \
    || echo "Warning: Whoop strain backfill failed — will retry on next startup."

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
