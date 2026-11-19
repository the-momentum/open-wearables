#!/bin/bash
# One-time initialization for a Redis-free, Apple-Health-only deploy.
#
# Run this once per deploy (e.g. as a Cloud Run Job) BEFORE/at rollout — it applies
# migrations and seeds the minimum required reference data. It deliberately skips the
# Svix database, outgoing webhook event-type registration, and provider-specific data
# migrations (Oura, etc.) that are not needed for an Apple-only, Redis-free deployment.
set -e -x

echo 'Applying migrations...'
uv run alembic upgrade head

echo 'Initializing provider settings...'
uv run python scripts/init_provider_settings.py

echo 'Initializing priorities...'
uv run python scripts/init_device_priorities.py

echo 'Seeding admin account...'
uv run python scripts/init/seed_admin.py

echo 'Initializing series type definitions...'
uv run python scripts/init/seed_series_types.py

echo 'Initializing archival settings...'
uv run python scripts/init/seed_archival_settings.py

echo 'Init complete.'
