#!/bin/bash
set -e -x

echo 'Applying migrations...'
/opt/venv/bin/alembic upgrade head

echo 'Initializing provider settings...'
/opt/venv/bin/python scripts/init_provider_settings.py

echo 'Initializing priorities...'
/opt/venv/bin/python scripts/init_device_priorities.py

echo 'Seeding admin account...'
/opt/venv/bin/python scripts/init/seed_admin.py

echo 'Initializing series type definitions...'
/opt/venv/bin/python scripts/init/seed_series_types.py
