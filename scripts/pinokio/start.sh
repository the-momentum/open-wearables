#!/bin/bash
set -e

echo '🚀 Starting Open Wearables...'
docker compose -f docker-compose.local.yml -p open-wearables-local up -d

echo '⏳ Waiting for services to be ready (15 seconds)...'
sleep 15

echo '🌱 Initializing database with sample data...'
docker compose -f docker-compose.local.yml -p open-wearables-local exec -T app uv run python scripts/init/main.py 2>/dev/null || echo 'ℹ️  Database already initialized or still starting'

echo ''
echo '✅ Open Wearables is running!'
echo ''
echo '📱 Dashboard: http://localhost:3001'
echo '📚 API Docs:  http://localhost:8001/docs'
echo ''
echo '👤 Default login: admin@admin.com / secret123'

