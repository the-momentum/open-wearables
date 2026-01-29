#!/bin/bash
set -e

echo '🚀 Starting Open Wearables...'
docker compose -f docker-compose.local.yml -p open-wearables-local up -d

echo '⏳ Waiting for services to be ready (20 seconds)...'
sleep 20

echo '🌱 Initializing database...'
# Seed admin user (creates admin@admin.com / secret123)
docker compose -f docker-compose.local.yml -p open-wearables-local exec -T app uv run python scripts/init/seed_admin.py 2>/dev/null || echo 'ℹ️  Admin already exists'

# Seed series types (health metric definitions)
docker compose -f docker-compose.local.yml -p open-wearables-local exec -T app uv run python scripts/init/seed_series_types.py 2>/dev/null || echo 'ℹ️  Series types already exist'

# Seed sample activity data (optional demo data)
docker compose -f docker-compose.local.yml -p open-wearables-local exec -T app uv run python scripts/init/seed_activity_data.py 2>/dev/null || echo 'ℹ️  Sample data already exists'

echo ''
echo '✅ Open Wearables is running!'
echo ''
echo '📱 Dashboard: http://localhost:3001'
echo '📚 API Docs:  http://localhost:8001/docs'
echo ''
echo '👤 Default login: admin@admin.com / secret123'
